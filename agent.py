# Core agent. The FSM (finite state machine) owns all hard rules: state transitions,
# retry limits, and payment sequencing. The LLM is only used for two things:
# extracting structured data from natural language, and generating responses.
# This split means policy cannot be accidentally overridden by the model.

import re
from state import ConversationState, State, AccountData
from llm import extract
from tools import lookup_account, process_payment
from verifier import verify_name, verify_secondary
from validators import luhn_check, validate_cvv, validate_expiry, validate_amount, parse_date
from prompts import (
    EXTRACT_ACCOUNT_ID, EXTRACT_NAME, EXTRACT_VERIFICATION_FACTOR,
    EXTRACT_AMOUNT, EXTRACT_CARD,
)

MAX_RETRIES = 3
MAX_INPUT_LENGTH = 500

SUPPORT_MSG = (
    "For security reasons, this session has been locked after multiple failed "
    "verification attempts. Please contact our support team at 1800-123-4567 for assistance."
)
TERMINAL_ERROR_MSG = (
    "We encountered an unexpected error. Please contact our support team at "
    "1800-123-4567 for assistance."
)


class Agent:
    def __init__(self):
        self._state = ConversationState()

    def next(self, user_input: str) -> dict:
        # Public interface: accepts one user message, returns {"message": <reply>}.
        # Input length is checked here before anything else touches the string.
        if len(user_input) > MAX_INPUT_LENGTH:
            return {"message": "That message is too long. Please keep your response brief."}
        self._state.history.append({"role": "user", "content": user_input})
        message = self._route(user_input)
        self._state.history.append({"role": "assistant", "content": message})
        return {"message": message}

    def _route(self, user_input: str) -> str:
        # Dispatch to the correct handler based on the current FSM state.
        # LOCKED and DONE are checked first because they are terminal.
        s = self._state.state
        if s == State.LOCKED:
            return SUPPORT_MSG
        if s == State.DONE:
            return "This session is complete. Thank you for using our service. Have a great day!"
        if s == State.GREETING:
            return self._handle_greeting(user_input)
        if s == State.LOOKUP:
            return self._handle_lookup(user_input)
        if s == State.VERIFY:
            return self._handle_verify(user_input)
        if s == State.BALANCE:
            return self._handle_balance(user_input)
        if s == State.COLLECT_PAYMENT:
            return self._handle_payment(user_input)
        return TERMINAL_ERROR_MSG

    def _handle_greeting(self, user_input: str) -> str:
        # Try to extract an account ID from the very first message.
        # If found, skip the prompt and go straight to lookup.
        extracted = extract(EXTRACT_ACCOUNT_ID.format(user_input=user_input))
        if extracted.get("account_id"):
            self._state.account_id = extracted["account_id"]
            self._state.state = State.LOOKUP
            return self._do_lookup()
        self._state.state = State.LOOKUP
        return "Hello! I'm here to help you with your payment. Could you please share your account ID to get started?"

    def _handle_lookup(self, user_input: str) -> str:
        if not self._state.account_id:
            extracted = extract(EXTRACT_ACCOUNT_ID.format(user_input=user_input))
            if not extracted.get("account_id"):
                return (
                    "I couldn't find an account ID in that message. "
                    "Your account ID should look like ACC1001. Could you please share it?"
                )
            self._state.account_id = extracted["account_id"]
        return self._do_lookup()

    def _do_lookup(self) -> str:
        # Call the lookup API and populate AccountData on success.
        # On 404 we clear the stored ID so the user can try again.
        # A network exception means all retries in tools._post were exhausted;
        # catch it here so the session can recover gracefully.
        try:
            data, status = lookup_account(self._state.account_id)
        except Exception:
            return "We're having trouble looking up your account right now. Please try again in a moment."
        if status == 404:
            bad_id = self._state.account_id
            self._state.account_id = None
            return (
                f"We couldn't find an account with ID {bad_id}. "
                "Please double-check and try again."
            )
        if status != 200:
            return "We're having trouble looking up your account right now. Please try again in a moment."
        self._state.account = AccountData(
            account_id=data["account_id"],
            full_name=data["full_name"],
            dob=data["dob"],
            aadhaar_last4=data["aadhaar_last4"],
            pincode=data["pincode"],
            balance=data["balance"],
        )
        self._state.state = State.VERIFY
        return "Got it. To verify your identity, could you please confirm your full name?"

    def _handle_verify(self, user_input: str) -> str:
        # Two-step verification: name first, then one secondary factor.
        # Each failed attempt increments retry_count; hitting MAX_RETRIES locks the session.
        account = self._state.account

        if not self._state.name_verified:
            extracted = extract(EXTRACT_NAME.format(user_input=user_input))
            name = extracted.get("full_name")
            if not name:
                return "I didn't catch your full name. Could you please share it?"
            if not verify_name(name, account):
                return self._fail_verify(
                    "That name doesn't match our records. Please double-check your full name."
                )
            self._state.name_verified = True
            return (
                "Thank you. To complete verification, could you please provide one of the following: "
                "your date of birth, the last 4 digits of your Aadhaar, or your pincode?"
            )

        extracted = extract(EXTRACT_VERIFICATION_FACTOR.format(user_input=user_input))
        factor_type = extracted.get("factor_type")
        value = extracted.get("value")

        if not factor_type or not value:
            return (
                "I couldn't extract a verification factor from that. "
                "Please provide your date of birth (e.g., 14 May 1990), "
                "last 4 digits of your Aadhaar, or your pincode."
            )

        if factor_type == "dob":
            parsed = parse_date(value)
            if not parsed:
                return "I couldn't parse that date. Please try again in a format like 14 May 1990 or 1990-05-14."
            value = parsed

        if not verify_secondary(factor_type, value, account):
            return self._fail_verify(
                "That doesn't match our records. Please try a different verification factor "
                "(date of birth, Aadhaar last 4, or pincode)."
            )

        self._state.verified = True
        self._state.state = State.BALANCE
        return self._handle_balance()

    def _fail_verify(self, message: str) -> str:
        self._state.retry_count += 1
        if self._state.retry_count >= MAX_RETRIES:
            self._state.state = State.LOCKED
            return SUPPORT_MSG
        remaining = MAX_RETRIES - self._state.retry_count
        return f"{message} ({remaining} attempt{'s' if remaining != 1 else ''} remaining)"

    def _handle_balance(self, user_input: str = "") -> str:
        # On first entry (user_input is empty) we announce the balance.
        # On subsequent turns for zero-balance accounts, we decline out-of-scope requests.
        balance = self._state.account.balance
        if balance == 0.0:
            if user_input:
                return (
                    "I can only assist with payment collection on this account. "
                    "Your balance is zero, so there is nothing to pay at this time."
                )
            return (
                "Identity verified. Your account currently has no outstanding balance, "
                "so there is nothing to pay at this time. Is there anything else I can help you with?"
            )
        self._state.state = State.COLLECT_PAYMENT
        return (
            f"Identity verified. Your outstanding balance is ₹{balance:,.2f}. "
            "How much would you like to pay today? You can pay the full amount or a partial amount."
        )

    def _handle_payment(self, user_input: str) -> str:
        # Amount is collected first, then card details across one or more turns.
        if not self._state.payment_amount:
            return self._collect_amount(user_input)
        return self._collect_card(user_input)

    def _collect_amount(self, user_input: str) -> str:
        extracted = extract(EXTRACT_AMOUNT.format(user_input=user_input))
        raw = extracted.get("amount")
        if raw == "full":
            amount = self._state.account.balance
        elif raw is None:
            return (
                f"How much would you like to pay? Your outstanding balance is "
                f"₹{self._state.account.balance:,.2f}. You can pay in full or a partial amount."
            )
        else:
            try:
                amount = float(raw)
            except (TypeError, ValueError):
                return "I couldn't understand that amount. Please enter a specific amount like 500 or 1000.75."

        ok, err = validate_amount(amount, self._state.account.balance)
        if not ok:
            if err == "insufficient_balance":
                return (
                    f"That amount exceeds your outstanding balance of "
                    f"₹{self._state.account.balance:,.2f}. Please enter a lower amount."
                )
            return "Please enter a valid amount. It should be positive and have no more than 2 decimal places."

        self._state.payment_amount = round(amount, 2)
        return "Got it. I'll need your card details. Please share your card number."

    def _collect_card(self, user_input: str) -> str:
        # Card details arrive across multiple turns. We tell the LLM which field
        # we are currently expecting so it can interpret bare values correctly.
        card = self._state.card

        if not card.card_number:
            expected_field = "card number"
        elif not card.expiry_month or not card.expiry_year:
            expected_field = "expiry date"
        elif not card.cvv:
            expected_field = "CVV (3 or 4 digits, returned as a string)"
        else:
            expected_field = "cardholder name"

        extracted = extract(EXTRACT_CARD.format(user_input=user_input, expected_field=expected_field))

        # LLMs often return null for bare digit strings like "123" even with field context.
        # Fall back to a direct regex match when the current field is CVV.
        if expected_field.startswith("CVV") and not extracted.get("cvv"):
            digits_only = re.sub(r"\D", "", user_input)
            if len(digits_only) in (3, 4):
                extracted["cvv"] = digits_only

        if extracted.get("card_number") and not card.card_number:
            num = "".join(d for d in extracted["card_number"] if d.isdigit())
            if not luhn_check(num):
                return "That card number doesn't look right. Could you double-check it?"
            card.card_number = num

        if extracted.get("expiry_month") and extracted.get("expiry_year") and not card.expiry_month:
            month = int(extracted["expiry_month"])
            year = int(extracted["expiry_year"])
            if not validate_expiry(month, year):
                return "That expiry date is invalid or the card has expired. Please check and try again."
            card.expiry_month = month
            card.expiry_year = year

        if extracted.get("cvv") and not card.cvv:
            cvv = str(extracted["cvv"])
            if card.card_number and not validate_cvv(cvv, card.card_number):
                return "The CVV doesn't look right. Please re-enter it."
            card.cvv = cvv

        if extracted.get("cardholder_name") and not card.cardholder_name:
            card.cardholder_name = extracted["cardholder_name"]

        if not card.card_number:
            return "Please share your card number."
        if not card.expiry_month or not card.expiry_year:
            return "What is the expiry date on your card? (e.g., December 2027 or 12/27)"
        if not card.cvv:
            return "What is the CVV on your card?"
        if not card.cardholder_name:
            return "What name is printed on the card?"

        return self._do_payment()

    def _do_payment(self) -> str:
        # Submit to the payment API. On specific card errors, clear the offending field
        # so the user can re-enter it without restarting the whole card collection flow.
        # A network exception means all retries were exhausted; end the session cleanly.
        try:
            data, status = process_payment(
                self._state.account.account_id,
                self._state.payment_amount,
                self._state.card,
            )
        except Exception:
            self._state.state = State.DONE
            return TERMINAL_ERROR_MSG

        if status == 200 and data.get("success"):
            self._state.transaction_id = data["transaction_id"]
            self._state.state = State.DONE
            return (
                f"Payment of ₹{self._state.payment_amount:,.2f} processed successfully! "
                f"Your transaction ID is {data['transaction_id']}. "
                "Thank you for your payment. Have a great day!"
            )

        error_code = data.get("error_code", "unknown")
        retryable = {
            "invalid_card": ("That card number doesn't look right. Could you double-check it?", "card_number"),
            "invalid_cvv": ("The CVV doesn't match. Please re-enter it.", "cvv"),
            "invalid_expiry": ("That expiry date is invalid or the card has expired. Please check and try again.", "expiry"),
        }
        if error_code in retryable:
            msg, field = retryable[error_code]
            if field == "card_number":
                self._state.card.card_number = None
            elif field == "cvv":
                self._state.card.cvv = None
            elif field == "expiry":
                self._state.card.expiry_month = None
                self._state.card.expiry_year = None
            return msg
        if error_code == "insufficient_balance":
            self._state.payment_amount = None
            return (
                f"The payment amount exceeds your balance of ₹{self._state.account.balance:,.2f}. "
                "Please enter a lower amount."
            )
        if error_code == "invalid_amount":
            self._state.payment_amount = None
            return "Please enter a valid amount. It should be positive and have no more than 2 decimal places."

        self._state.state = State.DONE
        return TERMINAL_ERROR_MSG
