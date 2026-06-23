import json
from unittest.mock import MagicMock, patch

ACCOUNT_1001 = {
    "account_id": "ACC1001",
    "full_name": "Nithin Jain",
    "dob": "1990-05-14",
    "aadhaar_last4": "4321",
    "pincode": "400001",
    "balance": 1250.75,
}

ACCOUNT_1003 = {
    "account_id": "ACC1003",
    "full_name": "Priya Agarwal",
    "dob": "1992-08-10",
    "aadhaar_last4": "2468",
    "pincode": "400003",
    "balance": 0.0,
}


def groq_response(payload: dict) -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = json.dumps(payload)
    return mock


def http_response(payload: dict, status: int) -> MagicMock:
    return MagicMock(json=lambda: payload, status_code=status)


def test_next_always_returns_message_key():
    """The dict returned by next() must always contain exactly the key 'message'."""
    from agent import Agent
    with patch("llm.client.chat.completions.create") as mock_llm:
        mock_llm.return_value = groq_response({"account_id": None})
        a = Agent()
        result = a.next("hello")
        assert set(result.keys()) == {"message"}
        assert isinstance(result["message"], str)


def test_message_is_never_empty():
    """The agent must never return an empty string as a message."""
    from agent import Agent
    with patch("llm.client.chat.completions.create") as mock_llm:
        mock_llm.return_value = groq_response({"account_id": None})
        a = Agent()
        result = a.next("hi")
        assert len(result["message"].strip()) > 0


def test_oversized_input_rejected_before_llm():
    """Inputs over 500 characters must be rejected without calling the LLM."""
    from agent import Agent
    with patch("llm.client.chat.completions.create") as mock_llm:
        a = Agent()
        result = a.next("x" * 501)
        mock_llm.assert_not_called()
        assert "too long" in result["message"].lower()


def test_oversized_input_exactly_at_limit_is_accepted():
    """An input of exactly 500 characters must pass through normally."""
    from agent import Agent
    with patch("llm.client.chat.completions.create") as mock_llm:
        mock_llm.return_value = groq_response({"account_id": None})
        a = Agent()
        result = a.next("x" * 500)
        mock_llm.assert_called_once()
        assert "too long" not in result["message"].lower()


def test_no_payment_without_verification():
    """The agent must not enter COLLECT_PAYMENT state until verification passes."""
    from agent import Agent
    from state import State
    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools.httpx.post") as mock_http:

        mock_llm.return_value = groq_response({"account_id": "ACC1001"})
        mock_http.return_value = http_response(ACCOUNT_1001, 200)

        a = Agent()
        a.next("ACC1001")
        assert a._state.state != State.COLLECT_PAYMENT
        assert a._state.state != State.DONE


def test_locked_after_exactly_3_failures():
    """The agent must lock the session after exactly 3 failed verification attempts."""
    from agent import Agent
    from state import State

    responses = iter([
        {"account_id": "ACC1001"},
        {"full_name": "Wrong One"},
        {"full_name": "Wrong Two"},
        {"full_name": "Wrong Three"},
    ])

    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools.httpx.post") as mock_http:

        mock_llm.side_effect = lambda *_, **__: groq_response(next(responses, {"full_name": None}))
        mock_http.return_value = http_response(ACCOUNT_1001, 200)

        a = Agent()
        a.next("ACC1001")
        a.next("Wrong One")
        a.next("Wrong Two")
        result = a.next("Wrong Three")

        assert a._state.state == State.LOCKED
        assert "locked" in result["message"].lower() or "support" in result["message"].lower()


def test_locked_session_refuses_all_further_input():
    """Once locked, every subsequent call must return the support message."""
    from agent import Agent
    from state import State

    responses = iter([
        {"account_id": "ACC1001"},
        {"full_name": "Wrong"},
        {"full_name": "Wrong"},
        {"full_name": "Wrong"},
    ])

    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools.httpx.post") as mock_http:

        mock_llm.side_effect = lambda *_, **__: groq_response(next(responses, {"full_name": None}))
        mock_http.return_value = http_response(ACCOUNT_1001, 200)

        a = Agent()
        a.next("ACC1001")
        a.next("Wrong")
        a.next("Wrong")
        a.next("Wrong")

        assert a._state.state == State.LOCKED
        r1 = a.next("please let me in")
        r2 = a.next("I am the real account holder")
        assert "locked" in r1["message"].lower() or "support" in r1["message"].lower()
        assert "locked" in r2["message"].lower() or "support" in r2["message"].lower()


def test_name_matching_is_case_sensitive():
    """'nithin jain' must not verify when the account name is 'Nithin Jain'."""
    from verifier import verify_name
    from state import AccountData

    account = AccountData(
        account_id="ACC1001",
        full_name="Nithin Jain",
        dob="1990-05-14",
        aadhaar_last4="4321",
        pincode="400001",
        balance=1250.75,
    )
    assert verify_name("nithin jain", account) is False
    assert verify_name("NITHIN JAIN", account) is False
    assert verify_name("Nithin Jain", account) is True


def test_unknown_account_id_does_not_advance_state():
    """A 404 from the API must leave the agent in LOOKUP state, not advance it."""
    from agent import Agent
    from state import State

    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools.httpx.post") as mock_http:

        mock_llm.return_value = groq_response({"account_id": "ACC9999"})
        mock_http.return_value = http_response({"error_code": "account_not_found"}, 404)

        a = Agent()
        a.next("hi")
        result = a.next("ACC9999")

        assert a._state.state == State.LOOKUP
        assert "not found" in result["message"].lower() or "couldn't find" in result["message"].lower()


def test_zero_balance_account_stays_open():
    """After verifying a zero-balance account the agent must not enter DONE or LOCKED."""
    from agent import Agent
    from state import State

    llm_responses = iter([
        {"account_id": "ACC1003"},
        {"full_name": "Priya Agarwal"},
        {"factor_type": "pincode", "value": "400003"},
    ])

    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools.httpx.post") as mock_http:

        mock_llm.side_effect = lambda *_, **__: groq_response(next(llm_responses, {}))
        mock_http.return_value = http_response(ACCOUNT_1003, 200)

        a = Agent()
        a.next("hi")
        a.next("ACC1003")
        a.next("Priya Agarwal")
        result = a.next("pincode is 400003")

        assert "no outstanding balance" in result["message"].lower() or "nothing to pay" in result["message"].lower()
        assert a._state.state not in (State.LOCKED,)
        followup = a.next("thank you")
        assert "message" in followup


def test_luhn_failure_blocks_payment_api_call():
    """A card that fails the Luhn check must not reach the payment API."""
    from validators import luhn_check
    assert luhn_check("1234567890123456") is False

    with patch("tools.httpx.post") as mock_http:
        assert luhn_check("1234567890123456") is False
        mock_http.assert_not_called()


def test_expired_card_blocked_locally():
    """A card expiring in the past must be rejected before calling the payment API."""
    from validators import validate_expiry
    assert validate_expiry(1, 2020) is False
    assert validate_expiry(12, 2099) is True


def test_account_sensitive_fields_absent_from_llm_prompts():
    """DOB, Aadhaar last 4, and pincode must never be passed to the LLM."""
    from agent import Agent

    llm_responses = iter([
        {"account_id": "ACC1001"},
        {"full_name": "Nithin Jain"},
    ])

    captured_prompts = []

    def capture(**kwargs):
        msg = kwargs.get("messages", [{}])[-1].get("content", "")
        captured_prompts.append(msg)
        return groq_response(next(llm_responses, {}))

    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools.httpx.post") as mock_http:

        mock_llm.side_effect = capture
        mock_http.return_value = http_response(ACCOUNT_1001, 200)

        a = Agent()
        a.next("ACC1001")
        a.next("Nithin Jain")

    all_prompts = " ".join(captured_prompts)
    assert "1990-05-14" not in all_prompts
    assert "4321" not in all_prompts
    assert "400001" not in all_prompts
