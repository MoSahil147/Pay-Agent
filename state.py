# All session state lives here. Nothing outside this file should invent new fields;
# every piece of data the agent needs during a call is tracked in ConversationState.

## __init__ helps to set up objects when we create them
from dataclasses import dataclass, field  # dataclass auto-generates __init__ and boilerplate; field() configures individual attributes (e.g. default_factory for mutable defaults)
from enum import Enum  # Enum gives the FSM states named constants instead of raw strings, preventing typos and making comparisons safe
from typing import Optional  # Optional[X] marks fields that may be None, documenting which pieces of state are not yet known


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
    state: State = State.GREETING # will start the FSM at the greeting Node
    account_id: Optional[str] = None # None until the user provides it; we then use it to make the API call
    account: Optional[AccountData] = None # Full account record we will store inside the account which we will get from the API
    verified: bool = False # start with false, once user verified will mark TRue
    retry_count: int = 0 # failed verification
    name_verified: bool = False # name verification
    payment_amount: Optional[float] = None # None until user says how much they want to pay
    card: CardData = field(default_factory=CardData) # field() with default_factory creates a fresh empty CardData every call so old card details never bleed into a new call
    transaction_id: Optional[str] = None # None until payment succeeds; the API sets this to confirm the transaction
    history: list = field(default_factory=list) # field() with default_factory gives a fresh empty list every call; grows with each message sent and received
    # Name extracted before the VERIFY state (e.g. volunteered in the same message
    # as the account ID). Used once in _handle_verify to avoid re-asking.
    pending_name: Optional[str] = None
