# Input validation for card details, payment amounts, and dates.
# All checks run locally before any API call is made, so bad data never reaches the network.

import re
from datetime import date, datetime
from typing import Optional


def luhn_check(card_number: str) -> bool:
    # Standard Luhn algorithm used by all major card networks to catch typos
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def is_amex(card_number: str) -> bool:
    # American Express cards start with 34 or 37 and use 4-digit CVVs
    clean = "".join(d for d in card_number if d.isdigit())
    return clean[:2] in ("34", "37")


def validate_cvv(cvv: str, card_number: str) -> bool:
    expected = 4 if is_amex(card_number) else 3
    return cvv.isdigit() and len(cvv) == expected


def validate_expiry(month: int, year: int) -> bool:
    if month < 1 or month > 12:
        return False
    today = date.today()
    if year < today.year:
        return False
    if year == today.year and month < today.month:
        return False
    return True


def validate_amount(amount: float, balance: float) -> tuple[bool, str]:
    if amount <= 0:
        return False, "invalid_amount"
    # Reject anything with more than 2 decimal places
    rounded = round(amount, 2)
    if abs(rounded - amount) > 1e-9:
        return False, "invalid_amount"
    if amount > balance:
        return False, "insufficient_balance"
    return True, ""


def parse_date(raw: str) -> Optional[str]:
    # Normalises a wide variety of user-provided date strings into YYYY-MM-DD.
    # Handles ordinal suffixes ("14th"), short years ("90"), and many common formats.
    raw = raw.strip()

    # Strip ordinal suffixes so "14th" becomes "14" before format matching
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", raw)

    # Expand two digit years such as "May 14, 90" into a full four digit year
    short_year_match = re.match(r"^([A-Za-z]+\s+\d{1,2},?\s+)(\d{2})$", cleaned)
    if short_year_match:
        prefix, yy = short_year_match.group(1).strip(), short_year_match.group(2)
        yy_int = int(yy)
        year = 1900 + yy_int if yy_int >= 0 else 2000 + yy_int
        cleaned = f"{prefix} {year}"
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

    formats_to_try = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
    ]

    for fmt in formats_to_try:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None
