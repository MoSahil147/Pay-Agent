# Thin wrapper around the Groq client. The rest of the codebase never imports
# groq directly; all LLM calls go through extract() or judge() here.

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Fast small model for structured extraction (account ID, name, card details, etc.)
EXTRACT_MODEL = "llama-3.1-8b-instant"

# Larger model reserved for the LLM-as-judge evaluation scorer
JUDGE_MODEL = "llama-3.3-70b-versatile"

# Use a placeholder key when running tests so the client can still be instantiated and mocked
api_key = os.environ.get("GROQ_API_KEY", "dummy-key-for-testing")
try:
    client = Groq(api_key=api_key)
except Exception:
    client = Groq(api_key="dummy-key-for-testing")


def extract(prompt: str) -> dict:
    # Returns an empty dict on any failure so callers can handle missing fields gracefully
    try:
        response = client.chat.completions.create(
            model=EXTRACT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}


def judge(prompt: str) -> dict:
    # Same pattern as extract() but uses the larger model for evaluation quality
    try:
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}
