# Identity verification logic. Name matching is intentionally case sensitive;
# the user must provide their name exactly as it appears on the account.

from state import AccountData


def verify_name(user_name: str, account: AccountData) -> bool:
    return user_name.strip() == account.full_name


def verify_secondary(factor_type: str, value: str, account: AccountData) -> bool:
    # The user provides exactly one of: date of birth, Aadhaar last 4, or pincode.
    # Any unknown factor type is treated as a failed check rather than an error.
    if factor_type == "dob":
        return value.strip() == account.dob
    if factor_type == "aadhaar_last4":
        return value.strip() == account.aadhaar_last4
    if factor_type == "pincode":
        return value.strip() == account.pincode
    return False
