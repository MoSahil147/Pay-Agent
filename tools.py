# HTTP calls to the external payment verification API.
# All requests go through _post(), which retries on transient network errors
# and logs at each stage without ever exposing card details.

import httpx
from state import CardData
import logger

BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com"

# Split timeouts: short connect window, longer read window to handle slow API responses
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

# Retry the request up to this many times on transient network errors
_MAX_RETRIES = 3


def _post(url: str, payload: dict) -> tuple[dict, int]:
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = httpx.post(url, json=payload, timeout=_TIMEOUT)
            return response.json(), response.status_code
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            logger.warning(f"Request to {url} failed on attempt {attempt} of {_MAX_RETRIES}: {type(exc).__name__}")
    logger.error(f"All {_MAX_RETRIES} attempts to {url} failed")
    raise last_exc  # type: ignore[misc]


def lookup_account(account_id: str) -> tuple[dict, int]:
    logger.info(f"Looking up account {account_id}")
    result = _post(f"{BASE_URL}/api/lookup-account", {"account_id": account_id})
    logger.info(f"Lookup for {account_id} returned status {result[1]}")
    return result


def process_payment(account_id: str, amount: float, card: CardData) -> tuple[dict, int]:
    # Card details are passed through but must not appear in logs; logger.py handles redaction
    payload = {
        "account_id": account_id,
        "amount": amount,
        "payment_method": {
            "type": "card",
            "card": {
                "cardholder_name": card.cardholder_name,
                "card_number": card.card_number,
                "cvv": card.cvv,
                "expiry_month": card.expiry_month,
                "expiry_year": card.expiry_year,
            },
        },
    }
    logger.info(f"Processing payment of {amount} for account {account_id}")
    result = _post(f"{BASE_URL}/api/process-payment", payload)
    logger.info(f"Payment for {account_id} returned status {result[1]}")
    return result
