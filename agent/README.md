# MedNexa agent

The AI receptionist: a LangGraph agent that understands the caller (English or
Hindi), calls tools backed by the backend's service layer, and returns a short reply for the
call pipeline to speak.

**Stack:** Python 3.11+ · LangGraph · LangChain (Ollama / Groq / OpenAI) · the
`mednexa-backend` package (editable path dependency) · uv

## Quick start

Prerequisites: the backend set up and seeded (see `backend/README.md`), and a model:
either [Ollama](https://ollama.com) with a tool-calling model, or a Groq/OpenAI API key.

```bash
ollama pull llama3.1:8b          # local model (or set a cloud key in .env)
cd agent
cp .env.example .env             # adjust models / keys
uv sync
uv run mednexa-chat              # talk to the agent in the terminal
```

`mednexa-chat` picks the first active hospital in the database and simulates a
caller (`--phone`, `--hospital-id` to override, `-v` to log routing and tools). Type
`/quit` to end the call and see the summary and outcome.

## Using it from the call pipeline

`MedNexaAgent` implements `telephony/telephony/agent_interface.py`'s
`AgentInterface`. Create one per call:

```python
from agent import MedNexaAgent

agent = MedNexaAgent(caller_phone, hospital_id)  # caller ID from telephony
greeting = await agent.get_greeting()
reply = await agent.process(text, language)  # language from STT ("en"/"hi")
summary = await agent.get_summary()

# When ending the call session:
await api.end_call(
    session_id,
    outcome=agent.call_outcome,
    summary=summary,
    escalated_to_human=agent.escalated,
    language_detected=agent.language,
)
```

- `call_outcome` is a backend `CallOutcome` value (`BOOKED`, `CANCELLED`,
  `RESCHEDULED`, `INFO_PROVIDED`, `ESCALATED`, `OTHER`).
- `escalated` is true when the agent handed the call to staff (`transfer_to_human`)
  or could not reach any model; the caller has been told to stay on the line.
- The agent reads the database directly, so the process running it needs
  `MEDNEXA_DATABASE_URL` and the `mednexa-agent` package installed.
- Farewell words ("goodbye", "धन्यवाद, नमस्ते") are only used in the final reply, so
  the pipeline's goodbye detection can end the call on them.

## How it works

```
caller text ──► agent node ──(tool calls)──► tools node ──► agent node … ──► guardrail ──► reply
                    │                            │
             ModelRouter                 app.services.contracts
        (Ollama or Groq/OpenAI)              (backend)
```

| Module | What it does |
|---|---|
| `router.py` | `ModelRouter`: local model under a latency cap, cloud on timeout/error, Hindi → cloud, circuit breaker after repeated local failures |
| `tools.py` | 11 tools over the service contract; caller phone and hospital come from the call, never the LLM |
| `graph.py` | LangGraph state machine with per-call memory and a tool-round limit |
| `prompts.py` | System prompt from the database: hospital, departments, doctors, today's free slots, call rules |
| `language.py` | Hindi/English detection (Devanagari, Hinglish, STT hint; Whisper's `ur` → `hi`) |
| `guardrails.py` | Blocks medical advice and booking/cancel/token claims not backed by a tool result; strips IDs; trims length |
| `events.py` | Records tool results for the summary, call outcome and grounding checks |
| `agent.py` | `MedNexaAgent`: greeting, turns, summary, outcome, failure handling |
| `evals.py` | Scenario runner against a real model |

### Tools

`get_hospital_info`, `list_doctors`, `get_doctor_details`, `check_available_slots`,
`find_next_available`, `book_appointment`, `get_my_appointments`,
`cancel_appointment`, `reschedule_appointment`, `get_current_datetime`,
`transfer_to_human`.

Each returns `{"ok": true, ...}` or `{"ok": false, "error": <code>, "message": ...}`;
business errors (slot taken, not the owner, …) are explained to the caller, never
raised. Bookings use the calling number; caller lookups, cancellations and
reschedules only see appointments registered to it.

## Configuration

All settings use the `MEDNEXA_AGENT_` prefix (see `.env.example`):

| Setting | Default | Meaning |
|---|---|---|
| `LLM_MODE` | `auto` | `auto`, `local` (never cloud) or `cloud` (never local) |
| `LOCAL_MODEL` / `OLLAMA_URL` | `llama3.1:8b` / `http://localhost:11434` | Ollama model |
| `LOCAL_CONTEXT_TOKENS` / `LOCAL_KEEP_ALIVE` | `8192` / `1h` | Context window for Ollama (its 4096 default cuts off long calls); how long the model stays loaded |
| `CLOUD_PROVIDER` / `CLOUD_MODEL` | `groq` / `openai/gpt-oss-20b` | Cloud model; only used when `GROQ_API_KEY` or `OPENAI_API_KEY` is set. Check the provider's current model list |
| `CLOUD_FALLBACK_MODELS` | `[]` | Groq models that answer when the main one is rate limited (each has its own per-minute limit) |
| `OPENAI_BASE_URL` | unset | With `CLOUD_PROVIDER=openai`, any OpenAI-compatible service, e.g. `https://api.featherless.ai/v1` |
| `CLOUD_REASONING_EFFORT` | unset | `low` makes gpt-oss models think briefly: faster replies, fewer tokens |
| `CLOUD_REQUEST_TIMEOUT_SECONDS` / `CLOUD_TIMEOUT_SECONDS` | `10` / `40` | One model request, and the whole answer including retries. A stalled request is abandoned and retried |
| `LLM_RETRIES` / `LLM_RETRY_DELAY_SECONDS` | `2` / `0.7` | Extra tries after a network error, a 5xx, a rate limit or a corrupt reply (the wait doubles each time). With fallback models, the next model answers at once instead |
| `HANDOVER_AFTER_FAILURES` | `3` | Turns in a row that fail before the caller is passed to staff. Until then the caller is asked to repeat and the call goes on |
| `CONFIRM_CHANGES` | `true` | Booking, cancelling, rescheduling and transferring need the caller's "yes" (see below) |
| `MAX_LATENCY_SECONDS` | `3` | Local calls slower than this fall back to cloud |
| `HINDI_PREFERS_CLOUD` | `true` | Send Hindi turns to the cloud model when available |
| `CIRCUIT_FAILURE_THRESHOLD` / `CIRCUIT_OPEN_SECONDS` | `3` / `300` | Skip local after repeated failures |
| `MAX_TOOL_ROUNDS` | `6` | Tool round trips per caller turn before forcing an answer |
| `MAX_RESPONSE_CHARS` | `600` | Spoken reply length cap |

## How changes are confirmed

A model can't be trusted to ask first, so the code does. The first `book_appointment`,
`cancel_appointment`, `reschedule_appointment` or `transfer_to_human` call only checks: it
changes nothing, and the receptionist asks the caller the exact details itself ("Just to
confirm: Rohan Mehta with Dr. Suresh Patel on Tuesday, 3 November at 9:50 AM. Shall I book
it?"), whatever the model wrote. The same call goes ahead only if the caller's next message is
a clear yes (English, Hindi or Hinglish; any "no" or "but" makes it not clear) and the details
are unchanged. A transfer the caller asked for ("let me talk to a person") is immediate.

After a successful change the receptionist says the result itself (time, token number), so
the details are exact and the turn needs one model call, not two.

## Testing

```bash
uv run pytest --cov          # needs the backend's dev Postgres (localhost:5434)
uv run ruff check . && uv run ruff format --check . && uv run mypy agent
```

Tests use a scripted LLM (`tests/fakes.py`), so they need no model or API key. They
run against a real Postgres database, `mednexa_agent_test`, which is created and
migrated automatically (override with `MEDNEXA_AGENT_TEST_DATABASE_URL`).

CI (`.github/workflows/agent.yml`) runs the same checks when `agent/`,
`backend/app/` or `backend/alembic/` change.

### Evaluating real models

```bash
cd backend && uv run python -m scripts.seed --reset
cd agent   && uv run python -m agent.evals                # or: ... agent.evals booking_hi
```

Runs scripted caller conversations (information, booking in English and Hindi,
medical-advice refusal, human handoff, appointment lookup) against the configured
model, checks the tools used and the call outcome, prints per-turn latency and
provider, and cancels anything it booked. Use it to compare models and prompt
changes.

## Troubleshooting

- **`No module named 'app'` or `'agent'` on macOS:** Python 3.13+ ignores `.pth`
  files with the macOS "hidden" flag, and folders synced by iCloud Drive (such as
  Desktop) can get that flag. Keep the repo outside iCloud-synced folders, or run
  with `PYTHONPATH=.:../backend`. Tests are unaffected (pytest sets the path).
- **Replies are slow:** check `[provider, ms]` in `mednexa-chat`. Lower
  `MAX_LATENCY_SECONDS` to fall back to the cloud sooner, or use a smaller local model.
