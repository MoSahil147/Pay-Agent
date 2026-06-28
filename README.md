# Pay-Agent

A conversational AI agent for end-to-end payment collection. The agent greets a user, looks up their account, verifies their identity, shares their outstanding balance, collects card payment details, processes the payment, and closes the session.

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/MoSahil147/Pay-Agent)

## Setup

1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone the repository and install dependencies:
   ```bash
   uv sync --extra dev
   ```

3. Copy `.env.example` to `.env` and add your Groq API key:
   ```bash
   cp .env.example .env
   # Edit .env and set GROQ_API_KEY=your_key_here
   ```

## Run Interactively

```bash
uv run python cli.py
```

## Run Tests

```bash
uv run pytest tests/ -v
```

## Run Evaluation

```bash
# Script-based evaluation
uv run python eval/runner.py

# With verbose transcripts
uv run python eval/runner.py --verbose

# With LLM-as-judge scoring (requires GROQ_API_KEY)
uv run python -c "
from eval.runner import run_all
from eval.judge import run_judge_on_all
results = run_all()
run_judge_on_all(results['results'])
"
```

## Test Accounts

| Account ID | Full Name | Balance |
|------------|-----------|---------|
| ACC1001 | Nithin Jain | ₹1,250.75 |
| ACC1002 | Rajarajeswari Balasubramaniam | ₹540.00 |
| ACC1003 | Priya Agarwal | ₹0.00 |
| ACC1004 | Rahul Mehta | ₹3,200.50 |

## Sample Conversations

### Successful Payment

```
You: Hi

Agent: Hello! I'm here to help you with your payment. Could you please share
your account ID to get started?

You: yeah my account number is ACC1001 I think

Agent: Got it. To verify your identity, could you please confirm your full name?

You: my name is Nithin Jain

Agent: Thank you. To complete verification, could you please provide one of the
following: your date of birth, the last 4 digits of your Aadhaar, or your
pincode?

You: DOB is 14th May 1990

Agent: Identity verified. Your outstanding balance is ₹1,250.75. How much
would you like to pay today?

You: I want to pay five hundred

Agent: Got it. I'll need your card details. Please share your card number.

You: the card number is 4532 0151 1283 0366

Agent: What is the expiry date on your card?

You: expires December 2027

Agent: What is the CVV on your card?

You: CVV is 123

Agent: What name is printed on the card?

You: Nithin Jain

Agent: Payment of ₹500.00 processed successfully! Your transaction ID is
txn_abc123. Thank you for your payment.
```

### Verification Failure: Account Locked After 3 Attempts

```
You: Hi

Agent: Hello! Could you please share your account ID?

You: ACC1001

Agent: Got it. Could you please confirm your full name?

You: John Doe

Agent: That name doesn't match our records. Please double-check.
(2 attempts remaining)

You: Jane Smith

Agent: That name doesn't match our records. (1 attempt remaining)

You: Wrong Person

Agent: For security reasons, this session has been locked after multiple failed
verification attempts. Please contact our support team at 1800-123-4567 for
assistance.
```

### Payment Failure: Invalid Card Number

```
...after successful verification...

Agent: Your outstanding balance is ₹1,250.75. How much would you like to pay?

You: 500

Agent: Please share your card number.

You: 1234567890123456

Agent: That card number doesn't look right. Could you double-check it?
```

### Payment Failure: Expired Card

```
...after successful verification...

Agent: Identity verified. Your outstanding balance is ₹1,250.75. How much
would you like to pay today?

You: 500

Agent: Got it. I'll need your card details. Please share your card number.

You: 4532 0151 1283 0366

Agent: What is the expiry date on your card? (e.g., December 2027 or 12/27)

You: March 2020

Agent: That expiry date is invalid or the card has expired. Please check
and try again.

You: December 2027

Agent: What is the CVV on your card?
```

### Edge Case: Zero Balance Account

```
You: Hi

Agent: Hello! Could you please share your account ID?

You: ACC1003

Agent: Got it. Could you please confirm your full name?

You: Priya Agarwal

Agent: Thank you. Could you please provide your date of birth, the last 4
digits of your Aadhaar, or your pincode?

You: pincode is 560001

Agent: Identity verified. Your account currently has no outstanding balance.
There is nothing to pay at this time. Is there anything else I can help you with?
```

## Architecture

The agent uses a hybrid FSM and LLM pattern. The finite state machine owns all hard rules: identity verification, retry limits, and payment sequencing. The LLM handles two things only: extracting structured data from natural language input, and generating natural language responses. See `docs/design.md` for details.

## Project Structure

```
Pay-Agent/
├── agent.py          # Agent class: FSM orchestration, public interface
├── llm.py            # Groq client wrapper for extraction and response generation
├── tools.py          # API calls: lookup_account, process_payment
├── verifier.py       # Verification logic: name match and secondary factor
├── validators.py     # Input validation: card number (Luhn), amount, date, CVV
├── state.py          # ConversationState dataclass and all session data
├── prompts.py        # All LLM prompt templates
├── cli.py            # Interactive CLI for manual testing
├── eval/
│   ├── runner.py     # Drives test scenarios against Agent.next()
│   ├── judge.py      # LLM-as-judge scorer
│   └── scenarios.py  # Test case definitions
├── tests/            # Unit and integration tests
├── pyproject.toml
├── uv.lock
└── docs/
    └── design.md     # Design document
```
