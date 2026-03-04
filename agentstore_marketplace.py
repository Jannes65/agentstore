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

    def run_agent(self, agent_id: str, input_str: str) -> ExecutionLog:
        """Executes an agent securely using SandboxedRunner."""
        listing = self.listings.get(agent_id)
        if not listing:
            raise ValueError(f"Agent '{agent_id}' not found in marketplace.")
        
        runner = SandboxedRunner(listing.adapter, listing.scope)
        return runner.run(input_str)

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
