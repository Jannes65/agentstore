from dataclasses import dataclass
from typing import List, Dict, Optional
from agentstore_schema import Category
from agentstore_adapter import AgentStoreAdapter, LangChainAdapter, CrewAIAdapter, AutoGenAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog, SandboxedRunner

from pydantic import BaseModel

import httpx
import re

async def call_agent_endpoint(endpoint_url: str, task: str, user_id: str, user_balance_sats: int = 0) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First attempt — no auth
            response = await client.post(endpoint_url, json={"task": task, "user_id": user_id})
            
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

    async def run_agent(self, agent_id: str, input_str: str, user_id: str = "anonymous") -> ExecutionLog:
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
            required_balance = price_sats
            
            # 2. Check user balance
            user_balance = get_balance(user_id)
            import logging
            logging.warning(f"Run agent balance check: user={user_id}, balance={user_balance}, required={required_balance} SATS")
            if user_balance < required_balance:
                raise ValueError(f"Insufficient balance. Required {required_balance} SATS")
            
            # 7. Execute agent (Attempt 1 - no payment yet)
            agent_response = await call_agent_endpoint(agent.endpoint_url, input_str, user_id, user_balance)
            
            # Handle L402 automatically
            if agent_response.get("status") == "l402_required":
                from agentstore_payments import pay_lightning_invoice
                lightning_invoice = agent_response.get("lightning_invoice")
                macaroon = agent_response.get("macaroon")
                
                # Pay the L402 invoice from user balance (This IS the agent run payment)
                payment_result = await pay_lightning_invoice(lightning_invoice, user_id, price_sats)
                if payment_result["status"] != "success":
                    output = "Insufficient balance for L402 payment"
                else:
                    # Credit builder 80%
                    credit_agent(agent_id, price_sats * 0.8)
                    
                    # Credit platform 18%
                    credit_agent("agentstore_platform", price_sats * 0.18)
                    
                    # Credit fee reserve 2%
                    credit_agent("agentstore_fees", price_sats * 0.02)
                    
                    preimage = payment_result.get("preimage")
                    # Retry the agent endpoint with the L402 Authorization header
                    headers = {"Authorization": f"L402 {macaroon}:{preimage}"}
                    retry_response = await call_agent_endpoint_with_auth(agent.endpoint_url, input_str, user_id, headers)
                    
                    if retry_response.get("status") == "success":
                        agent_response = retry_response # Update agent_response for logging
                        output = agent_response.get("result", "Agent finished without output.")
                    else:
                        output = retry_response.get("result", "Agent retry failed.")
            
            elif agent_response.get("status") == "success":
                # Deduct price from user (for direct success agents)
                deduct_balance(user_id, price_sats, agent_id=agent_id)
                
                # Credit builder 80%
                credit_agent(agent_id, price_sats * 0.8)
                
                # Credit platform 18%
                credit_agent("agentstore_platform", price_sats * 0.18)
                
                # Credit fee reserve 2%
                credit_agent("agentstore_fees", price_sats * 0.02)
                
                output = agent_response.get("result", "Agent finished without output.")
            else:
                output = agent_response.get("result", "Agent encountered an error.")

            # 8. Log transaction to ledger_transactions table
            # Only log if output was successfully obtained (either via L402 or direct success)
            if agent_response.get("status") == "success":
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
            
            # Ensure permissions_used is a list, not a dict (agent.permissions is JSON/dict)
            perms = agent.permissions or {}
            permissions_list = [k for k, v in perms.items() if v] if isinstance(perms, dict) else []
            
            return ExecutionLog(
                agent_id=agent_id,
                input_str=input_str,
                output=output,
                permissions_used=permissions_list
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
