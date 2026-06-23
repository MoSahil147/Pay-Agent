# Redacting logger. Every log line passes through redact() before it is written,
# so sensitive values (card numbers, CVV, DOB, Aadhaar, pincode) never appear in output.

import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("pay_agent")

# Patterns that identify sensitive values which must never appear in logs
_REDACT_PATTERNS = [
    (re.compile(r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b"), "****"),
    (re.compile(r'"cvv"\s*:\s*"\d{3,4}"'), '"cvv": "***"'),
    (re.compile(r'"dob"\s*:\s*"\d{4}-\d{2}-\d{2}"'), '"dob": "***"'),
    (re.compile(r'"aadhaar_last4"\s*:\s*"\d{4}"'), '"aadhaar_last4": "***"'),
    (re.compile(r'"pincode"\s*:\s*"\d{4,6}"'), '"pincode": "***"'),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def info(msg: str) -> None:
    logger.info(redact(str(msg)))


def warning(msg: str) -> None:
    logger.warning(redact(str(msg)))


def error(msg: str) -> None:
    logger.error(redact(str(msg)))
