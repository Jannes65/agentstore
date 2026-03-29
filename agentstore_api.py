from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import os
import time
import httpx
import logging
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
    agent_id = body.get("agent_id", "")
    engine_invoice_ref = body.get("engine_invoice_ref", "")
    
    # Verify payment confirmed via Chatabit
    if not engine_invoice_ref:
        return {"status": "error", "result": "No payment reference provided"}
    
    chatabit_url = os.environ.get("CHATABIT_URL", "https://www.bit-engage.com")
    api_key = os.environ.get("CHATABIT_API_KEY")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{chatabit_url}/subscriptionless-bridge/v1/invoices/{engine_invoice_ref}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        status_data = r.json()
    
    if status_data.get("status") != "paid":
        return {"status": "payment_required", "result": "Payment not confirmed"}
    
    # Fetch code from GitHub
    review_content = ""
    source = "direct"
    if github_url and "github.com" in github_url:
        try:
            parts = github_url.replace("https://github.com/", "").strip("/").split("/")
            owner, repo = parts[0], parts[1]
            
            if "/blob/" in github_url:
                # File-level URL — fetch directly
                raw_url = github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.get(raw_url)
                    review_content = r.text[:5000]
                    source = "github_file"
            else:
                # Repo-level URL — fetch top Python/JS files via GitHub API
                api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.get(api_url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "AgentStore-Review"})
                    if r.status_code != 200:
                        return {"status": "error", "result": f"Could not access repo: {r.status_code}"}
                    files = r.json()
                    key_files = [f for f in files if isinstance(f, dict) and 
                                f.get('name', '').endswith(('.py', '.js', '.ts')) and
                                f.get('type') == 'file'][:3]
                    combined = ""
                    for f in key_files:
                        fr = await client.get(f['download_url'])
                        combined += f"\n\n# File: {f['name']}\n{fr.text[:1500]}"
                    review_content = combined[:5000]
                    source = "github_repo"
        except Exception as e:
            return {"status": "error", "result": f"GitHub fetch error: {str(e)}"}
    
    if not review_content:
        return {"status": "error", "result": "Could not fetch code"}
    
    # Claude security review
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
                "max_tokens": 1500,
                "messages": [{
                    "role": "user",
                    "content": f"""You are a security auditor for AI agents on AgentStore marketplace.

Review this code for:
1. Security vulnerabilities
2. Data privacy issues
3. Malicious patterns
4. Permission overreach
5. Overall rating: SAFE / CAUTION / UNSAFE

GitHub: {github_url}
Code:
{review_content}

Format your response as:
RATING: [SAFE/CAUTION/UNSAFE]
SUMMARY: [2-3 sentences]
FINDINGS:
- [finding 1]
- [finding 2]
RECOMMENDATIONS:
- [recommendation 1]"""
                }]
            }
        )
        review_data = response.json()
        review_report = review_data["content"][0]["text"]
    
    logging.warning(f"Review rating: {review_report[:100]}")
    logging.warning(f"SAFE check: {'RATING: SAFE' in review_report}")
    logging.warning(f"CAUTION check: {'RATING: CAUTION' in review_report}")
    
    # Award badge based on rating
    badge_awarded = False
    badge_type = "none"
    if "RATING: SAFE" in review_report:
        from agentstore_database import SessionLocal, Agent
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if agent:
                agent.verified = True
                db.commit()
                badge_awarded = True
                badge_type = "verified"
        finally:
            db.close()
    elif "RATING: CAUTION" in review_report:
        from agentstore_database import SessionLocal, Agent
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if agent:
                agent.reviewed = True
                db.commit()
                logging.warning(f"Set reviewed=True for agent {agent_id}")
                badge_type = "reviewed"
        finally:
            db.close()
    
    return {
        "status": "success",
        "review_report": review_report,
        "badge_awarded": badge_awarded,
        "badge_type": badge_type,
        "rating": "SAFE" if "RATING: SAFE" in review_report else "CAUTION" if "RATING: CAUTION" in review_report else "UNSAFE"
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
    """Initialize database and ensure migrations."""
    init_db()
    
    # Migration: ensure schema
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE agents ADD COLUMN IF NOT EXISTS reviewed BOOLEAN DEFAULT FALSE"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS behaviour_logs (id SERIAL PRIMARY KEY, user_id VARCHAR, agent_id VARCHAR, agent_name VARCHAR, task VARCHAR, result_summary VARCHAR, cost_sats INTEGER DEFAULT 0, status VARCHAR DEFAULT 'success', created_at TIMESTAMP DEFAULT NOW())"))
            conn.execute(text("UPDATE agents SET endpoint_url = 'https://agentstore-production.up.railway.app/chat' WHERE name = 'AgentZero'"))
            conn.commit()
        except Exception:
            pass

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
    
    # Map to hide private keys
    safe_results = []
    for agent in results:
        a_dict = {
            "id": agent.id,
            "builder_id": agent.builder_id,
            "name": agent.name,
            "description_short": agent.description_short,
            "description_long": agent.description_long,
            "category": agent.category,
            "price_sats": agent.price_sats,
            "endpoint_url": agent.endpoint_url,
            "permissions": agent.permissions,
            "framework": agent.framework,
            "verified": agent.verified,
            "reviewed": agent.reviewed,
            "community_rating": agent.community_rating,
            "task_completion_rate": agent.task_completion_rate,
            "nostr_pubkey": agent.nostr_pubkey,
            "created_at": str(agent.created_at)
        }
        safe_results.append(a_dict)
    return safe_results

@app.get("/agents/top")
async def get_top_agents(db: Session = Depends(get_db)):
    """Returns top 5 agents by trust score."""
    from agentstore_database import Agent
    results = db.query(Agent).order_by(Agent.community_rating.desc()).limit(5).all()
    
    # Map to hide private keys
    safe_results = []
    for agent in results:
        a_dict = {
            "id": agent.id,
            "builder_id": agent.builder_id,
            "name": agent.name,
            "description_short": agent.description_short,
            "description_long": agent.description_long,
            "category": agent.category,
            "price_sats": agent.price_sats,
            "endpoint_url": agent.endpoint_url,
            "permissions": agent.permissions,
            "framework": agent.framework,
            "verified": agent.verified,
            "reviewed": agent.reviewed,
            "community_rating": agent.community_rating,
            "task_completion_rate": agent.task_completion_rate,
            "nostr_pubkey": agent.nostr_pubkey,
            "created_at": str(agent.created_at)
        }
        safe_results.append(a_dict)
    return safe_results

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Returns a single listing or 404."""
    agent = get_agent_db(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent listing not found")
    
    # Map to hide private keys
    return {
        "id": agent.id,
        "builder_id": agent.builder_id,
        "name": agent.name,
        "description_short": agent.description_short,
        "description_long": agent.description_long,
        "category": agent.category,
        "price_sats": agent.price_sats,
        "endpoint_url": agent.endpoint_url,
        "permissions": agent.permissions,
        "framework": agent.framework,
        "verified": agent.verified,
        "reviewed": agent.reviewed,
        "community_rating": agent.community_rating,
        "task_completion_rate": agent.task_completion_rate,
        "nostr_pubkey": agent.nostr_pubkey,
        "created_at": str(agent.created_at)
    }

@app.post("/agents/{agent_id}/publish-nostr")
async def publish_agent_nostr(agent_id: str, db: Session = Depends(get_db)):
    """Manually publish an existing agent to Nostr relays."""
    from agentstore_database import Agent
    from agentstore_nostr import publish_agent_to_nostr
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.nostr_privkey:
        raise HTTPException(status_code=400, detail="Agent has no Nostr keypair")

    # Prepare agent dict for publisher
    agent_dict = {
        "id": agent.id,
        "name": agent.name,
        "description_short": agent.description_short,
        "category": agent.category,
        "price_sats": agent.price_sats,
        "endpoint_url": agent.endpoint_url,
        "framework": agent.framework,
        "nostr_pubkey": agent.nostr_pubkey
    }
    
    success = publish_agent_to_nostr(agent_dict, agent.nostr_privkey)
    
    if success:
        return {"published": True}
    else:
        return {"published": False, "error": "Relay publication failed"}

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

@app.get("/users/{user_id}/history")
async def get_user_history(user_id: str):
    from agentstore_database import SessionLocal, BehaviourLog
    db = SessionLocal()
    try:
        logs = db.query(BehaviourLog).filter(
            BehaviourLog.user_id == user_id
        ).order_by(BehaviourLog.created_at.desc()).limit(50).all()
        return [{"id": l.id, "agent_name": l.agent_name, "task": l.task, 
                 "result_summary": l.result_summary, "cost_sats": l.cost_sats,
                 "status": l.status, "created_at": str(l.created_at)} for l in logs]
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
