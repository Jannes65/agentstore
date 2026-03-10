import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AutoGenAdapter, AgentStoreAdapter
from agentstore_marketplace import Listing
from agentstore_trust import PermissionScope, TrustScore
from agentstore_database import get_db, save_builder, get_builder as get_builder_db, save_agent, delete_agent_db, Builder

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

class WithdrawalRequest(BaseModel):
    lightning_invoice: str

class PriceUpdate(BaseModel):
    price_sats: int

@router.get("/builders/{builder_id}")
async def get_builder(builder_id: str, db: Session = Depends(get_db)):
    """Returns builder profile and their listed agents with detailed stats."""
    # Look up by builder_id column (which is 'id' in the Builder model)
    builder = db.query(Builder).filter(Builder.id == builder_id).first()
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
async def withdraw_earnings(builder_id: str, req: WithdrawalRequest, db: Session = Depends(get_db)):
    """Initiate Lightning payout for all agents owned by the builder."""
    builder = db.query(Builder).filter(Builder.id == builder_id).first()
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    # 1. Calculate total builder balance across all agents
    total_balance = 0
    agent_balances = []
    for agent in builder.agents:
        balance = get_agent_balance(agent.id)
        if balance > 0:
            total_balance += balance
            agent_balances.append((agent.id, balance))
    
    if total_balance <= 0:
        raise HTTPException(status_code=400, detail="No earnings to withdraw")

    # 2. In a real system, we'd verify the invoice amount matches total_balance here.
    # For this demo, we'll use Chatabit to 'pay' the builder. 
    # Note: Chatabit bridge v1 usually handles incoming payments (invoices we create).
    # Real payouts would use a different API or a Lightning node.
    # For now, we'll simulate the payout success and deduct balances.
    
    # Deduct from each agent wallet
    from agentstore_database import LedgerTransaction
    for agent_id, amount in agent_balances:
        deduct_agent(agent_id, amount, db=db)
        
        # Log withdrawal
        new_tx = LedgerTransaction(
            from_account=agent_id,
            to_account="external_builder_wallet",
            amount_sats=amount,
            transaction_type="withdrawal",
            agent_id=agent_id
        )
        db.add(new_tx)
    
    db.commit()
    
    return {"message": f"Successfully withdrew {total_balance} sats", "amount_sats": total_balance}

@router.get("/builders/{builder_id}/transactions")
async def get_builder_transactions(builder_id: str, db: Session = Depends(get_db)):
    """Returns transaction history for all agents owned by the builder."""
    builder = db.query(Builder).filter(Builder.id == builder_id).first()
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
