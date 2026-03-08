from dataclasses import dataclass
from typing import List, Dict, Optional
from agentstore_schema import Category
from agentstore_adapter import AgentStoreAdapter, LangChainAdapter, CrewAIAdapter, AutoGenAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog, SandboxedRunner

from pydantic import BaseModel

class Listing(BaseModel):
    """Represents an agent listing in the marketplace."""
    agent_id: str
    adapter: AgentStoreAdapter
    scope: PermissionScope
    trust_score: TrustScore
    price_sats: int
    category: Category

    model_config = {
        "arbitrary_types_allowed": True
    }

class Marketplace:
    """Manages agent listings and secure execution."""

    def __init__(self):
        self.listings: Dict[str, Listing] = {}

    def publish(self, listing: Listing):
        """Adds an agent listing to the marketplace."""
        self.listings[listing.agent_id] = listing

    def search(self, 
               category: Optional[Category] = None, 
               verified_only: bool = False, 
               max_price_sats: Optional[int] = None) -> List[Listing]:
        """Searches for agent listings based on criteria."""
        results = []
        for listing in self.listings.values():
            if category and listing.category != category:
                continue
            if verified_only and not listing.trust_score.verified:
                continue
            if max_price_sats is not None and listing.price_sats > max_price_sats:
                continue
            results.append(listing)
        return results

    def run_agent(self, agent_id: str, input_str: str, user_id: str = "anonymous") -> ExecutionLog:
        """Executes an agent securely with full payment flow."""
        from agentstore_database import SessionLocal, Agent, LedgerTransaction
        from agentstore_ledger import get_balance, deduct_balance, credit_agent
        import httpx
        
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                raise ValueError(f"Agent '{agent_id}' not found in database.")
            
            price_sats = agent.price_sats
            
            # 2. Check user balance
            user_balance = get_balance(user_id)
            if user_balance < price_sats:
                raise ValueError("Insufficient balance. Please top up.")
            
            # 4. Deduct full price from user
            deduct_balance(user_id, price_sats, agent_id=agent_id)
            
            # 5. Credit builder 80%
            credit_agent(agent_id, price_sats * 0.8)
            
            # 6. Credit platform 20%
            credit_agent("agentstore_platform", price_sats * 0.2)
            
            # 7. Execute agent
            output = ""
            if agent.endpoint_url:
                try:
                    # Attempt to call the real endpoint
                    import httpx
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            agent.endpoint_url,
                            json={"input": input_str},
                            headers={"Content-Type": "application/json"}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            output = data.get("output") or data.get("response") or str(data)
                        else:
                            output = f"Error from agent endpoint: {response.status_code}"
                except Exception as e:
                    output = f"Failed to connect to agent endpoint: {str(e)}"
            else:
                output = f"MOCK RESPONSE: Successfully executed agent {agent.name}. Your task '{input_str}' is complete."

            # 8. Log transaction to ledger_transactions table
            new_tx = LedgerTransaction(
                from_account=user_id,
                to_account=agent_id,
                amount_sats=price_sats,
                transaction_type="agent_run",
                agent_id=agent_id
            )
            db.add(new_tx)
            db.commit()

            # Return execution log
            from agentstore_trust import ExecutionLog
            return ExecutionLog(
                agent_id=agent_id,
                input_str=input_str,
                output=output,
                permissions_used=agent.permissions
            )
        finally:
            db.close()

    def top_rated(self, n: int = 5) -> List[Listing]:
        """Returns the top-rated agents sorted by trust score (community rating)."""
        # Sort by community_rating descending
        sorted_listings = sorted(
            self.listings.values(), 
            key=lambda x: x.trust_score.community_rating, 
            reverse=True
        )
        return sorted_listings[:n]

if __name__ == "__main__":
    marketplace = Marketplace()

    # 1. Publish 3 dummy agents
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

    # 2. Run a search
    print("--- Searching for Verified Productivity agents under 1000 sats ---")
    results = marketplace.search(category=Category.PRODUCTIVITY, verified_only=True, max_price_sats=1000)
    for res in results:
        print(f"Found: {res.agent_id} (Price: {res.price_sats} sats, Trust: {res.trust_score.badge()})")

    # 3. Execute one agent
    print("\n--- Executing 'lc_prod_01' via Marketplace ---")
    try:
        log = marketplace.run_agent("lc_prod_01", "How can I improve my productivity?")
        print(f"Agent Output: {log.output}")
        print(f"Execution Timestamp: {log.timestamp}")
        print(f"Permissions Used: {log.permissions_used}")
    except Exception as e:
        print(f"Execution failed: {e}")

    # 4. Show top rated
    print("\n--- Top Rated Agents ---")
    for top in marketplace.top_rated(2):
        print(f"{top.agent_id}: Rating {top.trust_score.community_rating}")
