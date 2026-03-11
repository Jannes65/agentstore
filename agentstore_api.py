from fastapi import FastAPI, HTTPException, Query, Depends, Request
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AutoGenAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog
from agentstore_marketplace import Marketplace, Listing
from sqlalchemy import text
from agentstore_database import init_db, get_db, save_agent, get_agent as get_agent_db, get_all_agents, save_execution_log, add_to_waitlist, Builder, engine
from agentstore_builder_api import router as builder_router
from agentstore_payments import create_invoice, check_payment
from agentstore_ledger import credit_balance, get_balance

app = FastAPI(title="AgentStore API")
app.include_router(builder_router)

# Add CORS middleware to allow the UI to fetch agents
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local testing, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global marketplace instance
marketplace = Marketplace()

# Waitlist Request Model
class WaitlistEntry(BaseModel):
    email: str
    name: str

# Request body model for running an agent
class RunInput(BaseModel):
    input: str
    user_id: str = "anonymous"

class DepositRequest(BaseModel):
    user_id: str
    amount_sats: int

@app.on_event("startup")
async def startup_event():
    """Initialize database and pre-populate with dummy agents if empty."""
    init_db()
    db = next(get_db())
    existing_agents = get_all_agents(db)
    if not existing_agents:
        # Agent 1: LangChain, Productivity, Verified
        agent1_data = {
            "id": "lc_prod_01",
            "name": "LangChain Productivity",
            "description_short": "Boost your productivity with LangChain.",
            "description_long": "A versatile LangChain agent for various productivity tasks.",
            "category": Category.PRODUCTIVITY.value,
            "price_sats": 500,
            "endpoint_url": "http://localhost:8001",
            "permissions": {"can_read_files": True},
            "framework": "langchain",
            "verified": True,
            "community_rating": 4.9,
            "task_completion_rate": 0.98
        }
        save_agent(db, agent1_data)

        # Agent 2: CrewAI, Research, Not Verified
        agent2_data = {
            "id": "crew_res_02",
            "name": "CrewAI Research",
            "description_short": "Advanced research via CrewAI.",
            "description_long": "Collaborative agent crew for deep research projects.",
            "category": Category.RESEARCH.value,
            "price_sats": 1200,
            "endpoint_url": "http://localhost:8002",
            "permissions": {"can_make_external_calls": True},
            "framework": "crewai",
            "verified": False,
            "community_rating": 4.2,
            "task_completion_rate": 0.85
        }
        save_agent(db, agent2_data)

        # Agent 3: AutoGen, Developer Tools, Verified
        agent3_data = {
            "id": "ag_dev_03",
            "name": "AutoGen Developer",
            "description_short": "Dev tools powered by AutoGen.",
            "description_long": "Streamline your development workflow with AutoGen agents.",
            "category": Category.DEVELOPER_TOOLS.value,
            "price_sats": 800,
            "endpoint_url": "http://localhost:8003",
            "permissions": {"can_read_files": True, "can_write_files": True},
            "framework": "autogen",
            "verified": True,
            "community_rating": 4.7,
            "task_completion_rate": 0.92
        }
        save_agent(db, agent3_data)
        
        # Agent 4: Built-in Test Agent
        agent4_data = {
            "id": "test_agent_04",
            "name": "Test Agent",
            "description_short": "Built-in test agent for verifying functionality.",
            "description_long": "A simple agent that responds to any task with a confirmation message. Useful for testing and debugging.",
            "category": Category.PRODUCTIVITY.value,
            "price_sats": 500,
            "endpoint_url": "https://agentstore-production.up.railway.app/agents/test-endpoint",
            "permissions": {},
            "framework": "builtin",
            "verified": True,
            "community_rating": 5.0,
            "task_completion_rate": 1.0
        }
        save_agent(db, agent4_data)

    # Always ensure test_agent_001 has the correct endpoint URL
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET endpoint_url = 'https://agentstore-production.up.railway.app/agents/test-l402-endpoint' WHERE id = 'test_agent_001'"))
        conn.commit()

@app.get("/agents")
async def get_agents(
    category: Optional[Category] = None, 
    verified_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Returns all listings with optional filtering."""
    results = get_all_agents(db, category=category.value if category else None, verified_only=verified_only)
    return results

@app.get("/agents/top")
async def get_top_agents(db: Session = Depends(get_db)):
    """Returns top 5 agents by trust score."""
    from agentstore_database import Agent
    results = db.query(Agent).order_by(Agent.community_rating.desc()).limit(5).all()
    return results

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Returns a single listing or 404."""
    agent = get_agent_db(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent listing not found")
    return agent

@app.post("/agents/{agent_id}/run", response_model=ExecutionLog)
async def run_agent(agent_id: str, run_input: RunInput, db: Session = Depends(get_db)):
    """Executes an agent securely with full payment flow."""
    from agentstore_marketplace import Marketplace
    marketplace = Marketplace()
    
    try:
        log = await marketplace.run_agent(agent_id, run_input.input, user_id=run_input.user_id)
        
        # Save log to DB
        save_execution_log(db, {
            "agent_id": agent_id,
            "input_str": run_input.input,
            "output": log.output,
            "permissions_used": log.permissions_used
        })
        
        return log
    except ValueError as e:
        if "Insufficient balance" in str(e):
            raise HTTPException(status_code=402, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_id}/balance")
async def get_agent_balance_api(agent_id: str):
    """Returns agent's accumulated earnings"""
    from agentstore_ledger import get_agent_balance
    balance = get_agent_balance(agent_id)
    return {"agent_id": agent_id, "balance_sats": balance}

@app.get("/builders/{builder_id}/earnings")
async def get_builder_earnings(builder_id: str, db: Session = Depends(get_db)):
    """Sum of all agent balances for that builder"""
    builder = db.query(Builder).filter(Builder.id == builder_id).first()
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    from agentstore_ledger import get_agent_balance
    total_earnings = 0
    agent_balances = {}
    
    for agent in builder.agents:
        balance = get_agent_balance(agent.id)
        total_earnings += balance
        agent_balances[agent.id] = balance
        
    return {
        "builder_id": builder_id,
        "total_earnings_sats": total_earnings,
        "agent_breakdown": agent_balances
    }

@app.post("/waitlist")
async def join_waitlist(entry: WaitlistEntry, db: Session = Depends(get_db)):
    """Adds a new user to the waitlist."""
    try:
        add_to_waitlist(db, entry.model_dump())
        return {"message": "Joined waitlist successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Email already exists or invalid data")

@app.post("/chat")
async def chat(request: dict):
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY"),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=request,
            timeout=30.0
        )
        result = response.json()
        print(f"Anthropic response status: {response.status_code}")
        print(f"Anthropic response: {result}")
        return result

@app.post("/payments/deposit")
async def deposit(req: DepositRequest):
    """Creates invoice, returns paymentRequest and engineInvoiceRef"""
    try:
        memo = f"Deposit for user {req.user_id}"
        # We use user_id as external_ref to identify the user on callback/status check
        invoice = await create_invoice(req.amount_sats, memo, req.user_id)
        return {
            "paymentRequest": invoice["payment_request"],
            "engineInvoiceRef": invoice["engine_invoice_ref"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payments/status/{engine_invoice_ref}")
async def payment_status(engine_invoice_ref: str, user_id: str, amount_sats: int):
    """Checks payment, if paid credits user balance"""
    try:
        status = await check_payment(engine_invoice_ref)
        if status.get("status") == "paid":
            import logging
            logging.warning(f"Crediting {amount_sats} sats to {user_id}")
            result = credit_balance(user_id, amount_sats)
            logging.warning(f"Credit result: {result}")
            return {"status": "paid", "balance_updated": True}
        return {"status": status.get("status", "pending")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payments/balance/{user_id}")
async def read_balance(user_id: str):
    """Returns current balance"""
    balance = get_balance(user_id)
    return {"user_id": user_id, "balance_sats": balance}

@app.post("/agents/test-endpoint")
async def test_agent_endpoint(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    task = body.get("task", "no task provided")
    return {
        "status": "success",
        "agent": "TestAgent",
        "result": f"I processed your task: '{task}'. This is a test response from AgentStore's built-in test agent.",
        "tokens_used": 42,
        "cost_sats": 500
    }

@app.post("/agents/test-l402-endpoint")
async def test_l402_endpoint(request: Request):
    # Check for L402 authorization
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("L402 "):
        # Return 402 with a fake invoice for testing
        return Response(
            status_code=402,
            headers={
                "WWW-Authenticate": 'L402 macaroon="test_macaroon_abc123", invoice="lnbc1test"'
            }
        )
    # Authorized — return result
    return {
        "status": "success",
        "agent": "L402TestAgent", 
        "result": "L402 payment verified! This agent was accessed via Lightning authentication."
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
