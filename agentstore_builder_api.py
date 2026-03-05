from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from agentstore_api import app, marketplace
from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AutoGenAdapter, AgentStoreAdapter
from agentstore_marketplace import Listing
from agentstore_trust import PermissionScope, TrustScore
from agentstore_database import get_db, save_builder, get_builder as get_builder_db, save_agent, delete_agent_db

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
async def register_builder(builder: BuilderRegistration, db: Session = Depends(get_db)):
    """Registers a new builder profile."""
    if get_builder_db(db, builder.builder_id):
        raise HTTPException(status_code=400, detail="Builder ID already exists")
    
    builder_data = builder.model_dump()
    save_builder(db, builder_data)
    return {"message": "Builder registered successfully", "builder_id": builder.builder_id}

@app.post("/agents/submit")
async def submit_agent(submission: AgentSubmission, db: Session = Depends(get_db)):
    """Submits a new agent to the marketplace."""
    from agentstore_database import get_agent
    if not get_builder_db(db, submission.builder_id):
        raise HTTPException(status_code=404, detail="Builder not found. Please register first.")
    
    if get_agent(db, submission.agent_id):
        raise HTTPException(status_code=400, detail="Agent ID already exists")

    agent_data = {
        "id": submission.agent_id,
        "builder_id": submission.builder_id,
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
    
    return {"message": "Agent submitted successfully", "agent_id": submission.agent_id}

@app.get("/builders/{builder_id}")
async def get_builder(builder_id: str, db: Session = Depends(get_db)):
    """Returns builder profile and their listed agents."""
    builder = get_builder_db(db, builder_id)
    if not builder:
        raise HTTPException(status_code=404, detail="Builder not found")
    
    return {
        "profile": {
            "builder_id": builder.id,
            "name": builder.name,
            "email": builder.email,
            "bitcoin_address": builder.bitcoin_address,
            "created_at": builder.created_at
        },
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "description_short": agent.description_short,
                "category": agent.category,
                "price_sats": agent.price_sats,
                "verified": agent.verified,
                "community_rating": agent.community_rating
            } for agent in builder.agents
        ]
    }

@app.delete("/agents/{agent_id}")
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
