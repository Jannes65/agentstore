from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import os
import time
import httpx
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
from agentstore_ledger import credit_balance, get_balance, deduct_balance

app = FastAPI(title="AgentStore API")
app.include_router(builder_router)

@app.post("/agents/{agent_id}/verify")
async def verify_agent(agent_id: str, request: Request):
    body = await request.json()
    review_report = body.get("review_report", "")
    github_url = body.get("github_url", "")
    
    from agentstore_database import SessionLocal, Agent
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        agent.verified = True
        db.commit()
        return {"status": "verified", "agent_id": agent_id}
    finally:
        db.close()

@app.post("/agents/review")
async def review_agent_code(request: Request):
    body = await request.json()
    github_url = body.get("github_url", "")
    code = body.get("code", "")
    agent_id = body.get("agent_id", "")
    user_id = body.get("user_id", "")
    
    # Check user has paid (500 sats)
    from agentstore_ledger import get_balance, deduct_balance
    balance = get_balance(user_id)
    if balance < 500:
        return {"status": "payment_required", "amount_sats": 500}
    
    # Fetch code from GitHub if URL provided
    review_content = code
    source = "direct_paste"
    if github_url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Convert GitHub URL to raw content
                raw_url = github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                r = await client.get(raw_url)
                review_content = r.text
                source = "github"
        except:
            review_content = code
    
    if not review_content:
        return {"status": "error", "result": "No code provided"}
    
    # Deduct 500 sats
    deduct_balance(user_id, 500)
    
    # Call Claude API for security review
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": f"""You are a security auditor for AI agents listed on AgentStore marketplace.
                    
Review this agent code for:
1. Security vulnerabilities
2. Data privacy issues  
3. Malicious patterns
4. Permission overreach
5. Overall safety rating (SAFE / CAUTION / UNSAFE)

Code source: {source}
{"GitHub URL: " + github_url if github_url else ""}

Code:
{review_content[:5000]}

Provide a concise security report with overall rating."""
                }]
            }
        )
        
        review_data = response.json()
        review_report = review_data["content"][0]["text"]
    
    # Award verified badge if source is GitHub and no critical issues
    badge_awarded = False
    if source == "github" and "UNSAFE" not in review_report:
        if agent_id:
            from agentstore_database import SessionLocal, Agent
            db = SessionLocal()
            try:
                agent = db.query(Agent).filter(Agent.id == agent_id).first()
                if agent:
                    agent.verified = True
                    db.commit()
                    badge_awarded = True
            finally:
                db.close()
    
    return {
        "status": "success",
        "review_report": review_report,
        "source": source,
        "badge_awarded": badge_awarded,
        "badge_type": "Verified ✅" if (badge_awarded and source == "github") else "Reviewed 🔍"
    }

# Add CORS middleware to allow the UI to fetch agents
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chooseyouragents.com",
        "https://twilight-hill-0366.jannes-4a6.workers.dev",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global marketplace instance
marketplace = Marketplace()

btc_price_cache = {"price": 0, "updated_at": 0}

@app.get("/btc-price")
async def get_btc_price():
    global btc_price_cache
    try:
        if time.time() - btc_price_cache["updated_at"] > 60:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
                btc_price_cache["price"] = r.json()["bitcoin"]["usd"]
                btc_price_cache["updated_at"] = time.time()
        return {"usd": btc_price_cache["price"]}
    except Exception as e:
        return {"usd": 85000}  # fallback price

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

    # Always ensure test_agent_001 has the correct endpoint URL and builder_id
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET endpoint_url = 'https://agentstore-production.up.railway.app/agents/test-endpoint' WHERE id = 'test_agent_001'"))
        conn.execute(text("UPDATE agents SET builder_id = 'jannes65' WHERE id = 'test_agent_001'"))
        conn.execute(text("UPDATE agent_balances SET balance_sats = 4800 WHERE agent_id = 'test_agent_001'"))
        conn.commit()

@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: Request):
    body = await request.json()
    from agentstore_database import SessionLocal, Agent
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if "price_sats" in body: agent.price_sats = int(body["price_sats"])
        if "description_short" in body: agent.description_short = body["description_short"]
        if "description_long" in body: agent.description_long = body["description_long"]
        if "category" in body: agent.category = body["category"]
        if "endpoint_url" in body: agent.endpoint_url = body["endpoint_url"]
        db.commit()
        return {"status": "updated", "agent_id": agent_id}
    finally:
        db.close()

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

@app.post("/agents/{agent_id}/run")
async def run_agent_endpoint(agent_id: str, request: Request):
    body = await request.json()
    user_id = body.get("user_id", "")
    task = body.get("task", "run")
    
    result = await marketplace.run_agent(agent_id, user_id, task)
    
    if result["status"] == "payment_required":
        return JSONResponse(status_code=402, content=result)
    
    return result

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
            logging.warning(f"Payment confirmed - crediting {amount_sats} sats to {user_id}")
            credit_result = credit_balance(user_id, amount_sats)
            logging.warning(f"credit_balance returned: {credit_result}")
            # Immediately verify
            balance = get_balance(user_id)
            logging.warning(f"Balance after credit: {balance}")
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

@app.post("/admin/reset-balance/{user_id}")
async def reset_balance(user_id: str):
    from agentstore_ledger import reset_user_balance
    reset_user_balance(user_id)
    return {"status": "reset", "user_id": user_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
