import os
import httpx
import logging
from typing import Optional
from agentstore_ledger import get_balance, deduct_balance

CHATABIT_API_KEY = os.environ.get("CHATABIT_API_KEY")
CHATABIT_URL = os.environ.get("CHATABIT_URL", "https://bit-engage.com")
BASE_URL = f"{CHATABIT_URL}/subscriptionless-bridge/v1"

import time
async def create_invoice(amount_sats: int, memo: str, user_id: str):
    """Calls POST {CHATABIT_URL}/subscriptionless-bridge/v1/invoices"""
    try:
        external_ref = f"{user_id}_{int(time.time())}"
        api_key = CHATABIT_API_KEY
        logging.warning(f"Auth header: Bearer {api_key[:15] if api_key else 'NONE'}...")
        async with httpx.AsyncClient(timeout=30.0) as client:
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
            data = response.json()
            return {
                "engine_invoice_ref": data["engineInvoiceRef"],
                "payment_request": data["paymentRequest"]
            }
    except Exception as e:
        import traceback
        logging.error(f"create_invoice error: {traceback.format_exc()}")
        raise

async def check_payment(engine_invoice_ref: str):
    """Calls GET {CHATABIT_URL}/subscriptionless-bridge/v1/invoices/:id"""
    api_key = CHATABIT_API_KEY
    logging.warning(f"Auth header: Bearer {api_key[:15] if api_key else 'NONE'}...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{BASE_URL}/invoices/{engine_invoice_ref}"
        logging.warning(f"Polling status URL: {url}")
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        logging.warning(f"Response: {response.status_code} {response.text}")
        response.raise_for_status()
        data = response.json()
        logging.warning(f"Chatabit status response: {data}")
        return data

async def pay_lightning_invoice(invoice: str, agent_id: str = "unknown") -> str:
    """Calls POST {CHATABIT_URL}/subscriptionless-bridge/v1/pay"""
    try:
        timestamp = int(time.time())
        external_ref = f"l402_{agent_id}_{timestamp}"
        api_key = CHATABIT_API_KEY
        
        logging.warning(f"Attempting to pay L402 invoice for agent {agent_id}")
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{BASE_URL}/pay",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "invoice": invoice,
                    "externalRef": external_ref
                }
            )
            
            if response.status_code != 200:
                logging.error(f"Chatabit payment failed: {response.status_code} {response.text}")
                raise Exception(f"Chatabit payment failed: {response.text}")
                
            data = response.json()
            preimage = data.get("preimage")
            if not preimage:
                logging.error(f"No preimage in Chatabit response: {data}")
                raise Exception("Chatabit payment succeeded but no preimage was returned")
                
            logging.warning(f"L402 payment successful for agent {agent_id}, preimage: {preimage[:10]}...")
            return preimage
    except Exception as e:
        logging.error(f"pay_lightning_invoice error: {str(e)}")
        raise
