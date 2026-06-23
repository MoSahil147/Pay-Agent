from unittest.mock import patch, MagicMock
import json


def make_groq_response(content: str):
    mock = MagicMock()
    mock.choices[0].message.content = content
    return mock


def test_extract_returns_dict():
    with patch("llm.client.chat.completions.create") as mock_create:
        mock_create.return_value = make_groq_response('{"account_id": "ACC1001"}')
        from llm import extract
        result = extract("some prompt")
        assert result == {"account_id": "ACC1001"}


def test_extract_uses_fast_model():
    with patch("llm.client.chat.completions.create") as mock_create:
        mock_create.return_value = make_groq_response('{"account_id": null}')
        from llm import extract, EXTRACT_MODEL
        extract("prompt")
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == EXTRACT_MODEL


def test_judge_uses_large_model():
    with patch("llm.client.chat.completions.create") as mock_create:
        mock_create.return_value = make_groq_response('{"policy_compliant": 1, "helpful": 1, "correct": 1, "reasoning": "ok"}')
        from llm import judge, JUDGE_MODEL
        judge("prompt")
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == JUDGE_MODEL


def test_extract_handles_json_parse_error():
    with patch("llm.client.chat.completions.create") as mock_create:
        mock_create.return_value = make_groq_response("not json at all")
        from llm import extract
        result = extract("prompt")
        assert result == {}
