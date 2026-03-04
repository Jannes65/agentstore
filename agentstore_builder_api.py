from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from agentstore_api import app, marketplace
from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AutoGenAdapter, AgentStoreAdapter
from agentstore_marketplace import Listing
from agentstore_trust import PermissionScope, TrustScore

# Storage for builders
builders: Dict[str, dict] = {}

class BuilderRegistration(BaseModel):
    builder_id: str
    name: str
    email: str
    bitcoin_address: str

class AgentSubmission(BaseModel):
    agent_id: str
    builder_id: str
    name: str
    description_short: str
    description_long: str
    category: str
    price_sats: int
    endpoint_url: str
    permissions: dict
    framework: str

@app.post("/builders/register")
async def register_builder(builder: BuilderRegistration):
    """Registers a new builder profile."""
    if builder.builder_id in builders:
        raise HTTPException(status_code=400, detail="Builder ID already exists")
    builders[builder.builder_id] = {
        "builder_id": builder.builder_id,
        "name": builder.name,
        "email": builder.email,
        "bitcoin_address": builder.bitcoin_address,
        "agents": []
    }
    return {"message": "Builder registered successfully", "builder_id": builder.builder_id}

@app.post("/agents/submit")
async def submit_agent(submission: AgentSubmission):
    """Submits a new agent to the marketplace."""
    if submission.builder_id not in builders:
        raise HTTPException(status_code=404, detail="Builder not found. Please register first.")
    
    if submission.agent_id in marketplace.listings:
        raise HTTPException(status_code=400, detail="Agent ID already exists")

    # Map framework to stub adapter
    framework_map = {
        "langchain": LangChainAdapter(),
        "crewai": CrewAIAdapter(),
        "autogen": AutoGenAdapter()
    }
    adapter = framework_map.get(submission.framework.lower())
    if not adapter:
        # Default to LangChain if unknown, but normally would raise error
        adapter = LangChainAdapter()

    # Parse permissions
    scope = PermissionScope(
        can_read_files=submission.permissions.get("can_read_files", False),
        can_write_files=submission.permissions.get("can_write_files", False),
        can_make_external_calls=submission.permissions.get("can_make_external_calls", False),
        can_access_env_vars=submission.permissions.get("can_access_env_vars", False)
    )

    # Initial trust score
    trust = TrustScore(
        agent_id=submission.agent_id,
        verified=False,
        community_rating=0.0,
        task_completion_rate=0.0
    )

    # Map category string to Category enum
    try:
        cat = Category(submission.category)
    except ValueError:
        cat = Category.OTHER

    listing = Listing(
        agent_id=submission.agent_id,
        adapter=adapter,
        scope=scope,
        trust_score=trust,
        price_sats=submission.price_sats,
        category=cat
    )

    marketplace.publish(listing)
    builders[submission.builder_id]["agents"].append(submission.agent_id)
    
    return {"message": "Agent submitted successfully", "agent_id": submission.agent_id}

@app.get("/builders/{builder_id}")
async def get_builder(builder_id: str):
    """Returns builder profile and their listed agents."""
    builder = builders.get(builder_id)
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    agent_details = []
    for agent_id in builder["agents"]:
        listing = marketplace.listings.get(agent_id)
        if listing:
            agent_details.append(listing.model_dump(exclude={'adapter'}))
            
    return {
        "profile": {k: v for k, v in builder.items() if k != "agents"},
        "agents": agent_details
    }

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, builder_id: str):
    """Builder can delist their agent."""
    if builder_id not in builders:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    if agent_id not in builders[builder_id]["agents"]:
        raise HTTPException(status_code=403, detail="Agent does not belong to this builder or not found")

    if agent_id in marketplace.listings:
        del marketplace.listings[agent_id]
    
    builders[builder_id]["agents"].remove(agent_id)
    return {"message": "Agent delisted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
