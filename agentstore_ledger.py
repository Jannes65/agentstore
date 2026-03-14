import os
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Session
from agentstore_database import Base, SessionLocal, UserBalance, AgentBalance, LedgerTransaction, DATABASE_URL
from sqlalchemy import create_engine, text

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    agent_id = Column(String, nullable=True)
    amount_sats = Column(Integer)
    transaction_type = Column(String)  # deposit/deduct/credit
    created_at = Column(DateTime, default=datetime.utcnow)

def credit_balance(user_id: str, amount_sats: int) -> dict:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(text("SELECT balance_sats FROM user_balances WHERE user_id = :uid"), {"uid": user_id}).fetchone()
        if result:
            new_balance = result[0] + amount_sats
            conn.execute(text("UPDATE user_balances SET balance_sats = :bal WHERE user_id = :uid"), {"bal": new_balance, "uid": user_id})
        else:
            new_balance = amount_sats
            conn.execute(text("INSERT INTO user_balances (user_id, balance_sats) VALUES (:uid, :bal)"), {"uid": user_id, "bal": new_balance})
        conn.commit()
    return {"status": "success", "new_balance": new_balance}

def deduct_balance(user_id: str, sats: int):
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT balance_sats FROM user_balances WHERE user_id = :uid"), {"uid": user_id}).fetchone()
        if not result or result[0] < sats:
            raise ValueError("Insufficient balance")
        
        new_balance = result[0] - sats
        conn.execute(text("UPDATE user_balances SET balance_sats = :bal WHERE user_id = :uid"), {"bal": new_balance, "uid": user_id})
        conn.commit()
    return True

def get_balance(user_id: str) -> int:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT balance_sats FROM user_balances WHERE user_id = :uid"), {"uid": user_id}).fetchone()
        return result[0] if result else 0

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

def deduct_agent(agent_id: str, sats: int, db: Optional[Session] = None):
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        agent_balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent_id).first()
        if not agent_balance or agent_balance.balance_sats < sats:
            raise ValueError("Insufficient agent balance")
        
        agent_balance.balance_sats -= sats
        db.commit()
    finally:
        if should_close:
            db.close()

def get_transactions(user_id: str = None, agent_id: str = None) -> list:
    db = SessionLocal()
    try:
        query = db.query(LedgerTransaction)
        if user_id:
            query = query.filter(LedgerTransaction.from_account == user_id)
        if agent_id:
            query = query.filter(LedgerTransaction.agent_id == agent_id)
        
        return query.order_by(LedgerTransaction.created_at.desc()).all()
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

def reset_user_balance(user_id: str):
    db = SessionLocal()
    try:
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        if balance:
            balance.balance_sats = 0
            db.commit()
    finally:
        db.close()
