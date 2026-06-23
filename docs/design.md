# Pay-Agent Design

## Architecture

The agent uses a hybrid finite state machine (FSM) and LLM pattern. The FSM owns all hard rules and state transitions. The LLM handles language only: extracting structured data from user input, and generating conversational responses.

```
User input
    |
Agent.next()
    |
FSM: current state?
    |
LLM (8b): extract structured data from input
    |
Python: validate, verify, call API
    |
FSM: advance state if conditions met
    |
LLM (70b): generate response
    |
{"message": "..."}
```

States progress in order: GREETING, LOOKUP, VERIFY, BALANCE, COLLECT_PAYMENT, DONE. A failed verification path leads to LOCKED, which is terminal.

The agent exposes a single public method:

```python
class Agent:
    def next(self, user_input: str) -> dict:
        # Returns {"message": str}
```

All session state is held in a `ConversationState` dataclass in memory between calls.

**Module layout:** `agent.py` orchestrates the FSM. `llm.py` wraps the Groq API. `tools.py` calls lookup and payment APIs. `verifier.py` handles name and secondary factor matching. `validators.py` runs Luhn checks, expiry parsing, CVV validation, and amount normalisation. `prompts.py` holds all LLM prompt templates. `state.py` defines the session state dataclass.

## Key Decisions

**Hybrid FSM over pure LLM.** A pure LLM agent risks skipping verification steps, leaking account data in responses, or losing retry counts across turns. The FSM makes all hard rules deterministic and independently testable. The LLM never decides what to do next -- it only translates between natural language and structured data.

**Two models for two jobs.** `llama-3.1-8b-instant` handles extraction: it is fast, cheap, and accurate enough for structured JSON output from well-constrained prompts. `llama-3.3-70b-versatile` handles response generation where quality matters more than speed.

**Exact name matching, no fuzzy logic.** The spec requires consistent verification behaviour. Fuzzy matching introduces ambiguity about when a match is close enough; exact matching is auditable and predictable. The tradeoff is that a user with a minor name typo on their account will fail verification.

**Account data never leaves Python.** DOB, Aadhaar last 4, and pincode are stored only in `ConversationState` and compared in deterministic Python. LLM prompts during verification contain only what the user just typed, not account fields. This prevents the LLM from accidentally surfacing sensitive data in its response.

**Zero balance stays open.** When a user lands on an account with no balance (ACC1003), the agent informs them and keeps the session open rather than closing immediately. Closing abruptly on a user who called in would be a worse experience.

## Tradeoffs Accepted

Groq with llama models is fast and free-tier accessible, but less capable than GPT-4o or Claude on ambiguous edge cases. The extraction prompts compensate for this with tight output schemas and examples, but unusual phrasing may still fail to parse correctly.

The exact name match requirement means a user who registered as "Raji Balasubramaniam" but says "Rajarajeswari Balasubramaniam" will fail. This is correct per the spec but would frustrate real users. A production system would want phonetic or normalised matching gated on risk tolerance.

The retry counter is session-scoped and in-memory. A user who reconnects gets a fresh session and a new set of three attempts. Rate limiting at the account level would require persistent storage.

## What Would Be Improved With More Time

Streaming responses would reduce perceived latency, since the LLM response generation on 70b is the slowest step.

Persistent session storage (Redis or similar) would allow resumable sessions and cross-session rate limiting on verification attempts per account.

Structured logging with field-level redaction would make it safe to capture full conversation transcripts for debugging without storing card numbers or identity fields in plain text.

The evaluator currently runs scenarios sequentially against a fresh agent instance each time. With more time it would support parallel execution, richer assertion types (regex on message content, not just terminal state checks), and a regression dashboard that tracks pass rates across prompt versions.

## Observations: Where the Agent Struggles

**CVV extraction from bare digit input.** When a user types only "123" at the CVV prompt, the LLM sometimes returns null even with field context in the prompt. A regex fallback was added as a safety net, but this highlights a broader issue: small extraction models are unreliable when the input is a short ambiguous string with no surrounding context.

**Expiry date split across turns.** If a user types "12" and then "2027" as separate messages, the agent asks again rather than combining them. The LLM cannot extract a valid expiry from a lone month or year number, so both messages are silently dropped. Users need to provide month and year together.

**Name matching is brittle by design.** Exact case-sensitive matching is required by the spec, which means a user who says "nithin jain" instead of "Nithin Jain" will fail verification. In a real deployment this would cause unnecessary friction and support calls.

**LLM extraction fails on heavy dialect or code-switching.** The extraction prompts are tuned for standard English. Users who mix languages, use regional phrasing, or spell out numbers in non-English words (for example "ek sau" for one hundred) will likely produce null extractions and get stuck in a retry loop.

**No cross-session rate limiting.** The retry counter resets with each new session. A bad actor can make unlimited verification attempts simply by reconnecting. Fixing this requires persistent storage keyed by account ID, which is outside the scope of this in-memory implementation.
