# All session state lives here. Nothing outside this file should invent new fields;
# every piece of data the agent needs during a call is tracked in ConversationState.

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class State(Enum):
    # The FSM moves through these states in order, top to bottom.
    # LOCKED and DONE are terminal: once reached, no further transitions happen.
    GREETING = "greeting"
    LOOKUP = "lookup"
    VERIFY = "verify"
    BALANCE = "balance"
    COLLECT_PAYMENT = "collect_payment"
    DONE = "done"
    LOCKED = "locked"


@dataclass
class AccountData:
    # Populated from the lookup API response. Stored in memory for the session only;
    # sensitive fields (dob, aadhaar_last4, pincode) are never passed to the LLM.
    account_id: str
    full_name: str
    dob: str
    aadhaar_last4: str
    pincode: str
    balance: float


@dataclass
class CardData:
    # Card details are collected one field at a time across multiple turns.
    # All fields start as None and are filled in as the user provides them.
    cardholder_name: Optional[str] = None
    card_number: Optional[str] = None
    cvv: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None


# dataclass is a python shortcut to autogenerate __init__ and other boilerplate so like we dont have to write manually
@dataclass # mem of one convo
class ConversationState:
    # The single source of truth for where the conversation is and what we know so far.
    state: State = State.GREETING
    account_id: Optional[str] = None # either String or NONE
    account: Optional[AccountData] = None # we dont get frpm the AccountData, mark None
    verified: bool = False
    retry_count: int = 0
    name_verified: bool = False
    payment_amount: Optional[float] = None
    card: CardData = field(default_factory=CardData) # defaultfactory is should be fresh per instance, to have no instance of old card data at all!
    transaction_id: Optional[str] = None
    history: list = field(default_factory=list)
    # Name extracted before the VERIFY state (e.g. volunteered in the same message
    # as the account ID). Used once in _handle_verify to avoid re-asking.
    pending_name: Optional[str] = None
