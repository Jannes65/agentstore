import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, JSON, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Database connection URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agentstore")

# Use SQLite as a fallback for local testing if needed, though instructions specify pg
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ORM Models ---

class Builder(Base):
    __tablename__ = "builders"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    bitcoin_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    agents = relationship("Agent", back_populates="builder")

class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, index=True)
    builder_id = Column(String, ForeignKey("builders.id"))
    name = Column(String)
    description_short = Column(String)
    description_long = Column(Text)
    category = Column(String)
    price_sats = Column(Integer)
    endpoint_url = Column(String)
    permissions = Column(JSON)  # Store PermissionScope as JSON
    agent_metadata = Column("metadata", JSON, default=dict) # Example tasks, task types, etc.
    framework = Column(String)
    verified = Column(Boolean, default=False)
    community_rating = Column(Float, default=0.0)
    task_completion_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    builder = relationship("Builder", back_populates="agents")

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    input_str = Column(Text)
    output = Column(Text)
    permissions_used = Column(JSON)

class Waitlist(Base):
    __tablename__ = "waitlist"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserBalance(Base):
    __tablename__ = "user_balances"
    user_id = Column(String, primary_key=True, index=True)
    balance_sats = Column(Integer, default=0)

class AgentBalance(Base):
    __tablename__ = "agent_balances"
    agent_id = Column(String, primary_key=True, index=True)
    balance_sats = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"
    id = Column(Integer, primary_key=True, index=True)
    from_account = Column(String, index=True)
    to_account = Column(String, index=True)
    amount_sats = Column(Integer)
    transaction_type = Column(String) # deposit/deduct/credit/agent_run
    agent_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

# --- CRUD Functions ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_builder(db: Session, builder_data: dict):
    # Map builder_id to id for the ORM model
    if "builder_id" in builder_data:
        builder_data["id"] = builder_data.pop("builder_id")
    db_builder = Builder(**builder_data)
    db.add(db_builder)
    db.commit()
    db.refresh(db_builder)
    return db_builder

def get_builder(db: Session, builder_id: str):
    return db.query(Builder).filter(Builder.id == builder_id).first()

def save_agent(db: Session, agent_data: dict):
    db_agent = Agent(**agent_data)
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

def get_agent(db: Session, agent_id: str):
    return db.query(Agent).filter(Agent.id == agent_id).first()

def get_all_agents(db: Session, category: Optional[str] = None, verified_only: bool = False):
    query = db.query(Agent)
    if category:
        query = query.filter(Agent.category == category)
    if verified_only:
        query = query.filter(Agent.verified == True)
    return query.all()

def delete_agent_db(db: Session, agent_id: str):
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if db_agent:
        db.delete(db_agent)
        db.commit()
        return True
    return False

def save_execution_log(db: Session, log_data: dict):
    db_log = ExecutionLog(**log_data)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def add_to_waitlist(db: Session, waitlist_data: dict):
    db_waitlist = Waitlist(**waitlist_data)
    db.add(db_waitlist)
    db.commit()
    db.refresh(db_waitlist)
    return db_waitlist
