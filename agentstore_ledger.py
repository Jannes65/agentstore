import os
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime
from agentstore_database import Base, SessionLocal, UserBalance, AgentBalance, LedgerTransaction

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    agent_id = Column(String, nullable=True)
    amount_sats = Column(Integer)
    transaction_type = Column(String)  # deposit/deduct/credit
    created_at = Column(DateTime, default=datetime.utcnow)

def credit_balance(user_id: str, sats: int, agent_id: Optional[str] = None):
    db = SessionLocal()
    try:
        # Update user balance
        user_balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        if not user_balance:
            user_balance = UserBalance(user_id=user_id, balance_sats=0)
            db.add(user_balance)
        
        user_balance.balance_sats += sats
        
        # Log to ledger
        ledger_entry = Ledger(
            user_id=user_id,
            agent_id=agent_id,
            amount_sats=sats,
            transaction_type="credit" if agent_id else "deposit"
        )
        db.add(ledger_entry)
        db.commit()
    finally:
        db.close()

def deduct_balance(user_id: str, sats: int, agent_id: Optional[str] = None):
    db = SessionLocal()
    try:
        user_balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        if not user_balance or user_balance.balance_sats < sats:
            raise ValueError("Insufficient balance")
        
        user_balance.balance_sats -= sats
        
        ledger_entry = Ledger(
            user_id=user_id,
            agent_id=agent_id,
            amount_sats=-sats,
            transaction_type="deduct"
        )
        db.add(ledger_entry)
        db.commit()
    finally:
        db.close()

def get_balance(user_id: str) -> int:
    db = SessionLocal()
    try:
        user_balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        return user_balance.balance_sats if user_balance else 0
    finally:
        db.close()

def get_agent_balance(agent_id: str) -> int:
    db = SessionLocal()
    try:
        agent_balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent_id).first()
        return agent_balance.balance_sats if agent_balance else 0
    finally:
        db.close()

def credit_agent(agent_id: str, sats: int):
    db = SessionLocal()
    try:
        agent_balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent_id).first()
        if not agent_balance:
            agent_balance = AgentBalance(agent_id=agent_id, balance_sats=0)
            db.add(agent_balance)
        
        agent_balance.balance_sats += int(sats)
        db.commit()
    finally:
        db.close()

def deduct_agent(agent_id: str, sats: int):
    db = SessionLocal()
    try:
        agent_balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent_id).first()
        if not agent_balance or agent_balance.balance_sats < sats:
            raise ValueError("Insufficient agent balance")
        
        agent_balance.balance_sats -= sats
        db.commit()
    finally:
        db.close()

def create_agent_wallet(agent_id: str):
    db = SessionLocal()
    try:
        agent_balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent_id).first()
        if not agent_balance:
            agent_balance = AgentBalance(agent_id=agent_id, balance_sats=0)
            db.add(agent_balance)
            db.commit()
    finally:
        db.close()
