from agentstore_database import SessionLocal, Agent
from agentstore_nostr import generate_agent_keypair

def backfill():
    db = SessionLocal()
    try:
        # Fetch all agents that don't have a nostr_pubkey
        agents_to_backfill = db.query(Agent).filter(Agent.nostr_pubkey == None).all()
        print(f"Found {len(agents_to_backfill)} agents to backfill.")
        
        for agent in agents_to_backfill:
            print(f"Backfilling agent: {agent.id} ({agent.name})")
            keys = generate_agent_keypair()
            agent.nostr_pubkey = keys["nostr_pubkey"]
            agent.nostr_privkey = keys["nostr_privkey"]
        
        db.commit()
        print("Backfill completed successfully.")
    except Exception as e:
        print(f"Error during backfill: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
