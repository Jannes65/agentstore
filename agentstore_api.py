from fastapi import FastAPI, HTTPException, Query, Depends
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
from agentstore_database import init_db, get_db, save_agent, get_agent as get_agent_db, get_all_agents, save_execution_log, add_to_waitlist

app = FastAPI(title="AgentStore API")

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
    """Executes an agent securely via SandboxedRunner."""
    db_agent = get_agent_db(db, agent_id)
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Reconstruct adapter and listing for SandboxedRunner
    framework_map = {
        "langchain": LangChainAdapter(),
        "crewai": CrewAIAdapter(),
        "autogen": AutoGenAdapter()
    }
    adapter = framework_map.get(db_agent.framework.lower(), LangChainAdapter())
    
    listing = Listing(
        agent_id=db_agent.id,
        adapter=adapter,
        scope=PermissionScope(**db_agent.permissions),
        trust_score=TrustScore(
            agent_id=db_agent.id,
            verified=db_agent.verified,
            community_rating=db_agent.community_rating,
            task_completion_rate=db_agent.task_completion_rate
        ),
        price_sats=db_agent.price_sats,
        category=Category(db_agent.category)
    )

    try:
        from agentstore_trust import SandboxedRunner
        runner = SandboxedRunner(listing.adapter, listing.scope)
        log = runner.run(run_input.input)
        
        # Save log to DB
        save_execution_log(db, {
            "agent_id": agent_id,
            "input_str": run_input.input,
            "output": log.output,
            "permissions_used": log.permissions_used
        })
        
        return log
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    import os
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
