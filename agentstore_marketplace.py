from dataclasses import dataclass
from typing import List, Dict, Optional
from agentstore_schema import Category
from agentstore_adapter import AgentStoreAdapter, LangChainAdapter, CrewAIAdapter, AutoGenAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog, SandboxedRunner

from pydantic import BaseModel

import httpx
import re

async def call_agent_endpoint(endpoint_url: str, task: str, user_id: str, user_balance_sats: int = 0) -> dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AgentStore/1.0"
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First attempt — no auth
            response = await client.post(endpoint_url, json={"task": task, "user_id": user_id}, headers=headers)
            
            # L402 handling
            if response.status_code == 402:
                # Extract Lightning invoice from WWW-Authenticate header
                auth_header = response.headers.get("WWW-Authenticate", "")
                invoice_match = re.search(r'invoice="([^"]+)"', auth_header)
                macaroon_match = re.search(r'macaroon="([^"]+)"', auth_header)
                
                if not invoice_match:
                    return {"status": "error", "result": "L402: No invoice found in 402 response"}
                
                lightning_invoice = invoice_match.group(1)
                macaroon = macaroon_match.group(1) if macaroon_match else ""
                
                return {
                    "status": "l402_required",
                    "lightning_invoice": lightning_invoice,
                    "macaroon": macaroon,
                    "result": "L402 payment required"
                }
            
            response.raise_for_status()
            return {"status": "success", "result": response.json()}
    except httpx.ConnectError:
        return {"status": "error", "result": "Could not connect to agent endpoint"}
    except httpx.TimeoutException:
        return {"status": "error", "result": "Agent endpoint timed out"}
    except Exception as e:
        return {"status": "error", "result": f"Agent error: {str(e)}"}

async def call_agent_endpoint_with_auth(endpoint_url: str, task: str, user_id: str, headers: dict) -> dict:
    # Ensure mandatory headers are present
    headers["Content-Type"] = "application/json"
    headers["User-Agent"] = "AgentStore/1.0"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint_url, json={"task": task, "user_id": user_id}, headers=headers)
            response.raise_for_status()
            return {"status": "success", "result": response.json()}
    except Exception as e:
        return {"status": "error", "result": f"Agent retry error: {str(e)}"}

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

    async def run_agent(self, agent_id, user_id, task):
        # 1. Get agent
        from agentstore_database import SessionLocal, Agent
        from agentstore_ledger import get_balance, deduct_balance, credit_agent, credit_balance
        from agentstore_payments import pay_lightning_invoice
        import logging

        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"status": "error", "result": "Agent not found"}
            
            # 2. Check balance — exactly price_sats, no buffer
            balance = get_balance(user_id)
            if balance < agent.price_sats:
                return {"status": "payment_required", "result": f"Insufficient balance. Required {agent.price_sats} SATS"}
            
            # 3. Deduct from user balance
            deduct_balance(user_id, agent.price_sats)
            
            # 4. Call agent endpoint
            try:
                # First attempt — no auth
                logging.warning(f"Starting execution of agent {agent_id} for user {user_id}")
                l402_res = await call_agent_endpoint(agent.endpoint_url, task, user_id)
                
                if l402_res.get("status") == "l402_required":
                    # L402 detected!
                    invoice = l402_res.get("lightning_invoice")
                    macaroon = l402_res.get("macaroon")
                    logging.warning(f"L402 detected for agent {agent_id}. Invoice: {invoice[:20]}...")
                    
                    # Call pay_lightning_invoice(invoice) → get preimage
                    try:
                        preimage = await pay_lightning_invoice(invoice, agent_id)
                        logging.warning(f"L402 payment successful, retrying with auth for agent {agent_id}")
                        
                        # Retry POST to endpoint_url with header: Authorization: L402 {macaroon}:{preimage}
                        auth_header = {"Authorization": f"L402 {macaroon}:{preimage}"}
                        retry_res = await call_agent_endpoint_with_auth(agent.endpoint_url, task, user_id, auth_header)
                        
                        if retry_res.get("status") != "success":
                            logging.error(f"L402 retry failed for agent {agent_id}: {retry_res.get('result')}")
                            # Refund user balance
                            credit_balance(user_id, agent.price_sats)
                            return retry_res
                        
                        result = retry_res.get("result")
                    except Exception as pay_err:
                        logging.error(f"L402 payment/retry error for agent {agent_id}: {str(pay_err)}")
                        # Refund user balance
                        credit_balance(user_id, agent.price_sats)
                        return {"status": "error", "result": f"L402 Error: {str(pay_err)}"}
                elif l402_res.get("status") == "success":
                    # Normal agent, no L402
                    result = l402_res.get("result")
                else:
                    # Error from call_agent_endpoint
                    credit_balance(user_id, agent.price_sats)
                    return l402_res
                    
            except Exception as e:
                # Refund on failure
                logging.error(f"Unexpected agent error for {agent_id}: {str(e)}")
                credit_balance(user_id, agent.price_sats)
                return {"status": "error", "result": f"Agent error: {str(e)}"}
            
            # 5. Credit builder 80%
            credit_agent(agent_id, int(agent.price_sats * 0.8))
            
            # 5.5 Log behaviour
            from agentstore_database import BehaviourLog
            try:
                log = BehaviourLog(
                    user_id=user_id,
                    agent_id=agent_id,
                    agent_name=agent.name,
                    task=task[:200] if task else "run",
                    result_summary=str(result)[:500] if result else "",
                    cost_sats=agent.price_sats,
                    status="success"
                )
                db.add(log)
                db.commit()
            except Exception as e:
                print(f"Failed to log behaviour: {e}")

            # 6. Return result
            return {"status": "success", "result": result}
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
        import asyncio
        log = asyncio.run(marketplace.run_agent("lc_prod_01", "How can I improve my productivity?"))
        print(f"Agent Output: {log.output}")
        print(f"Execution Timestamp: {log.timestamp}")
        print(f"Permissions Used: {log.permissions_used}")
    except Exception as e:
        print(f"Execution failed: {e}")

    # 4. Show top rated
    print("\n--- Top Rated Agents ---")
    for top in marketplace.top_rated(2):
        print(f"{top.agent_id}: Rating {top.trust_score.community_rating}")
