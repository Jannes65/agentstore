import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AutoGenAdapter, AgentStoreAdapter
from agentstore_marketplace import Listing
from agentstore_trust import PermissionScope, TrustScore
from agentstore_database import get_db, save_builder, get_builder as get_builder_db, save_agent, delete_agent_db, SessionLocal, Agent
from agentstore_ledger import get_agent_balance, deduct_agent

# Storage for builders (deprecated, using agentstore_database instead)
# builders: Dict[str, dict] = {}

router = APIRouter()

class BuilderRegister(BaseModel):
    name: str
    email: str
    bitcoin_address: str
    builder_id: Optional[str] = None

class AgentSubmission(BaseModel):
    agent_id: Optional[str] = None
    builder_id: Optional[str] = None
    name: str
    description_short: str
    description_long: str
    category: str
    price_sats: int
    endpoint_url: str
    permissions: dict = Field(default_factory=dict)
    framework: str

@router.post("/builders/register")
async def register_builder(builder: BuilderRegister, db: Session = Depends(get_db)):
    """Registers a new builder profile."""
    # Auto-generate builder_id if not provided
    if not builder.builder_id:
        builder.builder_id = str(uuid.uuid4())

    if get_builder_db(db, builder.builder_id):
        raise HTTPException(status_code=400, detail="Builder ID already exists")
    
    # Check if email already exists
    from agentstore_database import Builder
    if db.query(Builder).filter(Builder.email == builder.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    builder_data = builder.model_dump()
    # builder_id is mapped to id in save_builder
    save_builder(db, builder_data)
    return {"message": "Builder registered successfully", "builder_id": builder.builder_id}

@router.post("/agents/submit")
async def submit_agent(submission: AgentSubmission, db: Session = Depends(get_db)):
    """Submits a new agent to the marketplace."""
    from agentstore_database import get_agent
    
    # Use provided builder_id or create a default one
    builder_id = submission.builder_id or "default_builder"
    
    # Check if builder exists, if not create a default one
    if not get_builder_db(db, builder_id):
        # Generate a unique email to avoid conflicts if possible
        import random
        import string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        default_builder = {
            "builder_id": builder_id,
            "name": "Default Builder",
            "email": f"default_{builder_id}_{suffix}@example.com",
            "bitcoin_address": "default_address"
        }
        try:
            save_builder(db, default_builder)
        except Exception as e:
            # If it still fails, it's likely the builder_id (id in DB) conflict which shouldn't happen 
            # because we checked get_builder_db, or some other integrity error.
            print(f"Error creating default builder: {e}")
            pass
    
    # Auto-generate agent_id if not provided
    agent_id = submission.agent_id or str(uuid.uuid4())

    if get_agent(db, agent_id):
        raise HTTPException(status_code=400, detail="Agent ID already exists")

    agent_data = {
        "id": agent_id,
        "builder_id": builder_id,
        "name": submission.name,
        "description_short": submission.description_short,
        "description_long": submission.description_long,
        "category": submission.category,
        "price_sats": submission.price_sats,
        "endpoint_url": submission.endpoint_url,
        "permissions": submission.permissions,
        "framework": submission.framework,
        "verified": False,
        "community_rating": 0.0,
        "task_completion_rate": 0.0
    }

    save_agent(db, agent_data)
    
    # Auto-create agent wallet on submission
    from agentstore_ledger import create_agent_wallet
    create_agent_wallet(agent_id)
    
    return {"message": "Agent submitted successfully", "agent_id": agent_id}

from agentstore_ledger import get_agent_balance, deduct_agent, get_transactions
from agentstore_payments import create_invoice, check_payment

class WithdrawRequest(BaseModel):
    lightning_invoice: str

class WithdrawalRequest(BaseModel):
    lightning_invoice: str

class PriceUpdate(BaseModel):
    price_sats: int

@router.get("/builders/{builder_id}")
async def get_builder(builder_id: str, db: Session = Depends(get_db)):
    """Returns builder profile and their listed agents with detailed stats."""
    builder = get_builder_db(db, builder_id)
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    agent_list = []
    for agent in builder.agents:
        balance = get_agent_balance(agent.id)
        # Calculate run count from ledger transactions
        from agentstore_database import LedgerTransaction
        run_count = db.query(LedgerTransaction).filter(
            LedgerTransaction.agent_id == agent.id,
            LedgerTransaction.transaction_type == "agent_run"
        ).count()
        
        agent_list.append({
            "id": agent.id,
            "name": agent.name,
            "description_short": agent.description_short,
            "category": agent.category,
            "price_sats": agent.price_sats,
            "verified": agent.verified,
            "community_rating": agent.community_rating,
            "balance_sats": balance,
            "run_count": run_count,
            "status": "active" # Placeholder for now
        })
    
    return {
        "profile": {
            "builder_id": builder.id,
            "name": builder.name,
            "email": builder.email,
            "bitcoin_address": builder.bitcoin_address,
            "created_at": builder.created_at
        },
        "agents": agent_list
    }

@router.post("/builders/{builder_id}/withdraw")
async def withdraw_earnings(builder_id: str, withdraw: WithdrawRequest):
    import httpx, os
    from agentstore_ledger import get_agent_balance, deduct_agent, log_transaction
    from agentstore_database import SessionLocal, Agent
    
    lightning_invoice = withdraw.lightning_invoice.strip()
    
    if not lightning_invoice:
        raise HTTPException(status_code=400, detail="Lightning invoice required")
    
    # Get total earnings across all builder's agents
    db = SessionLocal()
    try:
        agents = db.query(Agent).filter(Agent.builder_id == builder_id).all()
        total_sats = sum(get_agent_balance(a.id) for a in agents)
        
        if total_sats < 1000:
            raise HTTPException(status_code=400, detail=f"Minimum withdrawal is 1000 sats. Current balance: {total_sats} sats")
        
        # Pay via Chatabit bridge
        api_key = os.environ.get("CHATABIT_API_KEY")
        import time
        external_ref = f"payout_{builder_id}_{int(time.time())}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create outbound payment
            response = await client.post(
                "https://chatabit.replit.app/subscriptionless-bridge/v1/pay",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "invoice": lightning_invoice,
                    "externalRef": external_ref
                }
            )
            
            logging.warning(f"Chatabit pay response: {response.status_code} {response.text}")
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Payment failed — check your Lightning invoice")
        
        # Deduct from agent balances proportionally
        pay_data = response.json()
        paid_amount = pay_data.get("amountSats", 1000)
        remaining = paid_amount
        
        for agent in agents:
            bal = get_agent_balance(agent.id)
            if bal > 0 and remaining > 0:
                deduct = min(bal, remaining)
                deduct_agent(agent.id, deduct)
                remaining -= deduct
                if remaining <= 0:
                    break
        
        # Log withdrawal to transaction history
        log_transaction(
            from_account=builder_id,
            to_account="lightning_payout",
            amount_sats=paid_amount,
            transaction_type="withdrawal",
            agent_id=None
        )
        
        return {
            "status": "success",
            "amount_sats": paid_amount,
            "message": f"Withdrawal of {paid_amount} sats sent successfully"
        }
    finally:
        db.close()

@router.get("/builders/{builder_id}/transactions")
async def get_builder_transactions(builder_id: str, db: Session = Depends(get_db)):
    """Returns transaction history for all agents owned by the builder."""
    builder = get_builder_db(db, builder_id)
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    all_transactions = []
    from agentstore_database import LedgerTransaction
    for agent in builder.agents:
        txs = db.query(LedgerTransaction).filter(LedgerTransaction.agent_id == agent.id).all()
        for tx in txs:
            all_transactions.append({
                "id": tx.id,
                "agent_id": tx.agent_id,
                "agent_name": agent.name,
                "amount_sats": tx.amount_sats,
                "type": tx.transaction_type,
                "created_at": tx.created_at
            })
    
    # Sort by date desc
    all_transactions.sort(key=lambda x: x["created_at"], reverse=True)
    return all_transactions

@router.patch("/agents/{agent_id}/price")
async def update_agent_price(agent_id: str, update: PriceUpdate, db: Session = Depends(get_db)):
    """Updates the price of an agent."""
    from agentstore_database import get_agent
    agent = get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.price_sats = update.price_sats
    db.commit()
    return {"message": "Price updated successfully", "new_price": agent.price_sats}

@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, builder_id: str, db: Session = Depends(get_db)):
    """Builder can delist their agent."""
    from agentstore_database import get_agent
    builder = get_builder_db(db, builder_id)
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    agent = get_agent(db, agent_id)
    if not agent or agent.builder_id != builder_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to this builder or not found")

    delete_agent_db(db, agent_id)
    return {"message": "Agent delisted successfully"}

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8000)
