import json
import os

from groq import Groq
from dotenv import load_dotenv

import logger

load_dotenv()

EXTRACT_MODEL = "llama-3.1-8b-instant"
JUDGE_MODEL = "llama-3.3-70b-versatile"

client = Groq(api_key=os.environ.get("GROQ_API_KEY", "dummy-key-for-testing"))


def _call(model: str, prompt: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning(f"LLM returned non-JSON from {model}: {exc}")
        return {}
    except Exception as exc:
        logger.warning(f"LLM call to {model} failed: {type(exc).__name__}: {exc}")
        return {}


def extract(prompt: str) -> dict:
    return _call(EXTRACT_MODEL, prompt)


def judge(prompt: str) -> dict:
    return _call(JUDGE_MODEL, prompt)
