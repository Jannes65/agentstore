import os
import httpx
from typing import Optional

CHATABIT_API_KEY = os.environ.get("CHATABIT_API_KEY")
BASE_URL = "https://chatabit.replit.app/subscriptionless-bridge/v1"

async def create_invoice(amount_sats: int, memo: str, external_ref: str):
    """Calls POST https://chatabit.replit.app/subscriptionless-bridge/v1/invoices"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/invoices",
            headers={"x-api-key": CHATABIT_API_KEY},
            json={
                "amount": amount_sats,
                "memo": memo,
                "external_ref": external_ref
            }
        )
        response.raise_for_status()
        return response.json()

async def check_payment(engine_invoice_ref: str):
    """Calls GET https://chatabit.replit.app/subscriptionless-bridge/v1/invoices/:id"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/invoices/{engine_invoice_ref}",
            headers={"x-api-key": CHATABIT_API_KEY}
        )
        response.raise_for_status()
        return response.json()
