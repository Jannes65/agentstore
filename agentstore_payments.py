import os
import httpx
import logging
from typing import Optional

CHATABIT_API_KEY = os.environ.get("CHATABIT_API_KEY")
BASE_URL = "https://chatabit.replit.app/subscriptionless-bridge/v1"

async def create_invoice(amount_sats: int, memo: str, external_ref: str):
    """Calls POST https://chatabit.replit.app/subscriptionless-bridge/v1/invoices"""
    try:
        api_key = CHATABIT_API_KEY
        logging.warning(f"Auth header: Bearer {api_key[:15] if api_key else 'NONE'}...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/invoices",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "amountSats": amount_sats,
                    "memo": memo,
                    "externalRef": external_ref
                }
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        import traceback
        logging.error(f"create_invoice error: {traceback.format_exc()}")
        raise

async def check_payment(engine_invoice_ref: str):
    """Calls GET https://chatabit.replit.app/subscriptionless-bridge/v1/invoices/:id"""
    api_key = CHATABIT_API_KEY
    logging.warning(f"Auth header: Bearer {api_key[:15] if api_key else 'NONE'}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/invoices/{engine_invoice_ref}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        return response.json()
