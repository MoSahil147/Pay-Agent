# Changes

Production-readiness improvements made after an audit of the codebase. Changes are
grouped by the issue they address.

---

## Fix 3: LLM failures now surface in logs

**File:** `llm.py`

Previously, any exception thrown by the Groq client (auth errors, quota exhaustion,
network timeouts) was caught alongside `json.JSONDecodeError` and silently discarded.
The caller received an empty dict with no indication anything had gone wrong, making
quota breaches and credential issues invisible in production.

The two exception branches are now separated. A `json.JSONDecodeError` is logged at
WARNING level with the raw error. Any other exception (network, auth, rate limit) is
also logged at WARNING with its type and message. Both branches still return an empty
dict so caller behaviour is unchanged.

---

## Fix 1: Deduplicated LLM call logic

**File:** `llm.py`

`extract()` and `judge()` were identical functions aside from the model name. A shared
private `_call(model, prompt)` function now holds the implementation. Both public
functions delegate to it. This means logging and error handling only need to be
updated in one place.

---

## Fix 6: Network failures no longer crash the session

**File:** `agent.py`

`tools._post` raises the last caught exception when all retries are exhausted. Neither
`_do_lookup` nor `_do_payment` previously handled this, meaning a prolonged API
outage would propagate an unhandled exception all the way through `agent.next()` and
crash the caller's process.

Both methods now wrap their tool calls in a `try/except Exception` block:

- `_do_lookup`: returns the existing "trouble looking up your account" message.
- `_do_payment`: transitions the session to DONE and returns the terminal error message.

The session ends cleanly in both cases rather than raising.

---

## Fix 4: HTTP connection pooling

**File:** `tools.py`

`httpx.post` was called as a module-level function, which opens a new TCP connection
and performs a full TLS handshake on every request. Under any meaningful call rate
this adds measurable latency and wastes file descriptors on both sides.

A single module-level `httpx.Client` instance (`_client`) is now shared across all
calls. The client reuses existing connections from its internal pool. The same timeout
configuration as before is passed at construction time.

Tests that previously patched `tools.httpx.post` have been updated to patch
`tools._client.post` instead.

---

## Fix 5: Retry backoff with jitter

**File:** `tools.py`

The retry loop in `_post` previously retried immediately with no delay between
attempts. Three back-to-back requests to an overloaded or rate-limited upstream is
the worst possible recovery strategy.

Between each failed attempt the loop now sleeps for `0.5 * 2^(attempt-1)` seconds
plus a small random jitter (0 to 0.25 s). The delays are therefore roughly 0.5 s
then 1.0 s before the third and final attempt. No sleep is added after the last
failure since the exception is raised immediately.

---

## Fix 10: Logger no longer pollutes the root logger

**File:** `logger.py`

`logging.basicConfig()` configures the root logger, which affects every library
loaded in the same process. Any third-party package that uses standard logging would
have its output reformatted or its level changed as a side effect of importing
`logger.py`.

The call to `basicConfig` has been removed. A `StreamHandler` with the same format
string is now attached directly to the `pay_agent` named logger. `propagate` is set
to `False` so log records do not travel up to the root logger at all. The logger can
now be silenced in tests without disturbing other libraries.

---

## Fix 11: Eval runner now checks intermediate turns

**File:** `eval/runner.py`

`step_accuracy` was computed by counting correct turns, but intermediate turns (all
turns except the last) were unconditionally marked correct regardless of what the
agent actually said. Only the final turn was ever evaluated. This meant
`step_accuracy` was always at least `(n-1)/n`, masking broken intermediate
behaviour.

A `_check_stage(message, expected_stage)` function now evaluates each intermediate
turn with loose keyword checks matched to the expected conversation stage. A turn
that clearly does not match its expected stage is marked incorrect and sets the
scenario to failed with a descriptive reason pointing to the offending turn number.

The `expected_stage` field in each scenario turn, which was previously described as
"informational only", now actually drives evaluation.
