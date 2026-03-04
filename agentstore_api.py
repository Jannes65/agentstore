from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
from pydantic import BaseModel

from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AutoGenAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog
from agentstore_marketplace import Marketplace, Listing

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

# Request body model for running an agent
class RunInput(BaseModel):
    input: str

@app.on_event("startup")
async def startup_event():
    """Pre-populate the marketplace with dummy agents on startup."""
    # Agent 1: LangChain, Productivity, Verified
    agent1 = Listing(
        agent_id="lc_prod_01",
        adapter=LangChainAdapter(),
        scope=PermissionScope(can_read_files=True),
        trust_score=TrustScore(agent_id="lc_prod_01", verified=True, community_rating=4.9, task_completion_rate=0.98),
        price_sats=500,
        category=Category.PRODUCTIVITY
    )
    marketplace.publish(agent1)

    # Agent 2: CrewAI, Research, Not Verified
    agent2 = Listing(
        agent_id="crew_res_02",
        adapter=CrewAIAdapter(),
        scope=PermissionScope(can_make_external_calls=True),
        trust_score=TrustScore(agent_id="crew_res_02", verified=False, community_rating=4.2, task_completion_rate=0.85),
        price_sats=1200,
        category=Category.RESEARCH
    )
    marketplace.publish(agent2)

    # Agent 3: AutoGen, Developer Tools, Verified
    agent3 = Listing(
        agent_id="ag_dev_03",
        adapter=AutoGenAdapter(),
        scope=PermissionScope(can_read_files=True, can_write_files=True),
        trust_score=TrustScore(agent_id="ag_dev_03", verified=True, community_rating=4.7, task_completion_rate=0.92),
        price_sats=800,
        category=Category.DEVELOPER_TOOLS
    )
    marketplace.publish(agent3)

@app.get("/agents")
async def get_agents(
    category: Optional[Category] = None, 
    verified_only: bool = Query(False)
):
    """Returns all listings with optional filtering."""
    results = marketplace.search(category=category, verified_only=verified_only)
    # Convert to dict and exclude adapter for serialization
    return [listing.model_dump(exclude={'adapter'}) for listing in results]

@app.get("/agents/top")
async def get_top_agents():
    """Returns top 5 agents by trust score."""
    results = marketplace.top_rated(5)
    return [listing.model_dump(exclude={'adapter'}) for listing in results]

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Returns a single listing or 404."""
    listing = marketplace.listings.get(agent_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Agent listing not found")
    return listing.model_dump(exclude={'adapter'})

@app.post("/agents/{agent_id}/run", response_model=ExecutionLog)
async def run_agent(agent_id: str, run_input: RunInput):
    """Executes an agent securely via SandboxedRunner."""
    try:
        log = marketplace.run_agent(agent_id, run_input.input)
        return log
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
