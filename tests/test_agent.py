from unittest.mock import patch, MagicMock
import json

ACCOUNT_DATA = {
    "account_id": "ACC1001", "full_name": "Nithin Jain",
    "dob": "1990-05-14", "aadhaar_last4": "4321",
    "pincode": "400001", "balance": 1250.75
}


def make_groq_response(content):
    mock = MagicMock()
    mock.choices[0].message.content = json.dumps(content) if isinstance(content, dict) else content
    return mock


def test_agent_greeting():
    from agent import Agent
    a = Agent()
    result = a.next("Hi")
    assert "message" in result
    assert isinstance(result["message"], str)
    assert len(result["message"]) > 0


def test_agent_returns_dict_with_message_key():
    from agent import Agent
    a = Agent()
    result = a.next("hello")
    assert set(result.keys()) == {"message"}


def test_agent_extracts_account_id_from_first_message():
    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools._client.post") as mock_http:

        mock_llm.return_value = make_groq_response({"account_id": "ACC1001"})
        mock_http.return_value = MagicMock(json=lambda: ACCOUNT_DATA, status_code=200)

        from agent import Agent
        a = Agent()
        result = a.next("my account is ACC1001")
        assert "name" in result["message"].lower() or "verify" in result["message"].lower()


def test_agent_handles_unknown_account():
    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools._client.post") as mock_http:

        mock_llm.return_value = make_groq_response({"account_id": "ACC9999"})
        mock_http.return_value = MagicMock(
            json=lambda: {"error_code": "account_not_found"}, status_code=404
        )

        from agent import Agent
        a = Agent()
        a.next("Hi")
        result = a.next("ACC9999")
        assert "not found" in result["message"].lower() or "couldn't find" in result["message"].lower()


def test_agent_locks_after_3_failed_verifications():
    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools._client.post") as mock_http:

        call_count = [0]
        def llm_side_effect(**kwargs):
            call_count[0] += 1
            content = kwargs.get("messages", [{}])[-1].get("content", "")
            if "account" in content.lower() or call_count[0] == 1:
                return make_groq_response({"account_id": "ACC1001"})
            return make_groq_response({"full_name": "Wrong Name"})

        mock_llm.side_effect = lambda **kwargs: llm_side_effect(**kwargs)
        mock_http.return_value = MagicMock(json=lambda: ACCOUNT_DATA, status_code=200)

        from agent import Agent
        a = Agent()
        a.next("Hi")
        a.next("ACC1001")
        a.next("Wrong Name")
        a.next("Wrong Name Again")
        result = a.next("Still Wrong Name")
        assert "locked" in result["message"].lower() or "support" in result["message"].lower()


def test_agent_zero_balance_informs_and_stays_open():
    zero_account = {**ACCOUNT_DATA, "account_id": "ACC1003", "balance": 0.0}
    with patch("llm.client.chat.completions.create") as mock_llm, \
         patch("tools._client.post") as mock_http:

        responses = iter([
            {"account_id": "ACC1003"},
            {"full_name": "Nithin Jain"},
            {"factor_type": "dob", "value": "1990-05-14"},
        ])
        mock_llm.side_effect = lambda *_, **__: make_groq_response(next(responses, {"account_id": None}))
        mock_http.return_value = MagicMock(json=lambda: zero_account, status_code=200)

        from agent import Agent
        a = Agent()
        a.next("Hi")
        a.next("ACC1003")
        a.next("Nithin Jain")
        result = a.next("DOB 1990-05-14")
        assert "no outstanding balance" in result["message"].lower() or "nothing to pay" in result["message"].lower()
        # The agent should remain open and accept further messages after informing the user
        followup = a.next("okay thanks")
        assert "message" in followup
