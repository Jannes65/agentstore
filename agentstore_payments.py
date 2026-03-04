from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog
from agentstore_marketplace import Marketplace, Listing

# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class PaymentMethod(str, Enum):
    LIGHTNING = "LIGHTNING"
    ONCHAIN   = "ONCHAIN"
    FIAT      = "FIAT"

# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class PaymentRequest(BaseModel):
    """Represents a request for payment in the AgentStore."""
    agent_id: str
    amount_sats: int
    payment_method: PaymentMethod
    invoice_id: str
    status: str = "pending"  # pending/paid/expired
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# ─────────────────────────────────────────────
# STUBS
# ─────────────────────────────────────────────

class LightningPaymentStub:
    """A stub for interacting with a Bitcoin Lightning Node/API."""

    def create_invoice(self, agent_id: str, amount_sats: int) -> PaymentRequest:
        """Generates a stub Lightning invoice for an agent payment."""
        # Stub: invoice_id would be a real Bolt11 string or similar
        invoice_id = f"lnbc_{agent_id}_{int(datetime.now().timestamp())}"
        return PaymentRequest(
            agent_id=agent_id,
            amount_sats=amount_sats,
            payment_method=PaymentMethod.LIGHTNING,
            invoice_id=invoice_id,
            status="pending"
        )

    def check_payment(self, invoice_id: str) -> bool:
        """Stub that simulates payment confirmation."""
        # Stub: always return True to indicate successful payment
        return True

    def payout_to_builder(self, builder_id: str, amount_sats: int, split: float = 0.80) -> dict:
        """Calculates 80/20 split and returns payout summary."""
        builder_share = int(amount_sats * split)
        platform_fee = amount_sats - builder_share
        
        return {
            "builder_id": builder_id,
            "builder_share_sats": builder_share,
            "platform_fee_sats": platform_fee,
            "currency": "SATS",
            "payout_status": "processed",
            "timestamp": datetime.now().isoformat()
        }

# ─────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────

class PaymentRouter:
    """Wraps payment logic and integrates with the Marketplace."""

    def __init__(self, marketplace: Marketplace):
        self.marketplace = marketplace
        self.lightning_stub = LightningPaymentStub()

    def purchase_and_run(self, agent_id: str, input_str: str, payment_method: PaymentMethod) -> dict:
        """
        Coordinates the purchase and execution flow:
        creates invoice -> confirms payment -> runs agent -> returns log and receipt
        """
        listing = self.marketplace.listings.get(agent_id)
        if not listing:
            raise ValueError(f"Agent '{agent_id}' not found in marketplace.")

        # 1. Create invoice
        payment_request = self.lightning_stub.create_invoice(agent_id, listing.price_sats)
        print(f"[*] Invoice created: {payment_request.invoice_id} for {payment_request.amount_sats} SATS")

        # 2. Confirm payment (stub)
        is_paid = self.lightning_stub.check_payment(payment_request.invoice_id)
        if not is_paid:
            payment_request.status = "expired"
            raise ConnectionError("Payment failed or timed out.")
        
        payment_request.status = "paid"
        print(f"[*] Payment confirmed for {payment_request.invoice_id}")

        # 3. Run agent via Marketplace's SandboxedRunner
        execution_log = self.marketplace.run_agent(agent_id, input_str)
        print(f"[*] Agent '{agent_id}' executed successfully.")

        # 4. Process builder payout (stub)
        author_name = "Agent Builder" # In a real scenario, this would come from the manifest/listing
        payout_receipt = self.lightning_stub.payout_to_builder(author_name, listing.price_sats)

        return {
            "execution_log": execution_log,
            "payment_receipt": {
                "invoice_id": payment_request.invoice_id,
                "amount_sats": payment_request.amount_sats,
                "status": payment_request.status,
                "payout_summary": payout_receipt
            }
        }

# ─────────────────────────────────────────────
# MAIN BLOCK
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # 1. Setup Marketplace with an agent
    marketplace = Marketplace()
    agent = Listing(
        agent_id="lc_prod_01",
        adapter=LangChainAdapter(),
        scope=PermissionScope(can_read_files=True),
        trust_score=TrustScore(agent_id="lc_prod_01", verified=True, community_rating=4.9, task_completion_rate=0.98),
        price_sats=500,
        category=Category.PRODUCTIVITY
    )
    marketplace.publish(agent)

    # 2. Setup Payment Router
    router = PaymentRouter(marketplace)

    # 3. Demo Purchase-and-Run Flow
    print("--- Starting Purchase-and-Run Flow (500 SATS) ---")
    try:
        result = router.purchase_and_run(
            agent_id="lc_prod_01",
            input_str="Optimize my calendar for high-focus work.",
            payment_method=PaymentMethod.LIGHTNING
        )

        log = result["execution_log"]
        receipt = result["payment_receipt"]

        print("\n--- Final Receipt ---")
        print(f"Status: {receipt['status']}")
        print(f"Invoice: {receipt['invoice_id']}")
        print(f"Amount Paid: {receipt['amount_sats']} SATS")
        print(f"Builder Payout: {receipt['payout_summary']['builder_share_sats']} SATS")
        print(f"Platform Fee: {receipt['payout_summary']['platform_fee_sats']} SATS")

        print("\n--- Execution Log ---")
        print(f"Output: {log.output}")
        print(f"Permissions: {log.permissions_used}")

    except Exception as e:
        print(f"Flow failed: {e}")
