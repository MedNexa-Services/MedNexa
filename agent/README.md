# MedNexa Agent (Part 2)

The AI receptionist: a LangGraph agent that understands the caller (English or
Hindi), calls tools backed by Part 1's service layer, and returns a short reply for
Part 3 to speak.

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

## Using it from the call pipeline (Part 3)

`MedNexaAgent` implements `telephony/telephony/agent_interface.py`'s
`AgentInterface`. Create one per call:

```python
from agent import MedNexaAgent

agent = MedNexaAgent(caller_phone, hospital_id)   # caller ID from telephony
greeting = await agent.get_greeting()
reply = await agent.process(text, language)        # language from STT ("en"/"hi")
summary = await agent.get_summary()

# When ending the call session:
await api.end_call(session_id, outcome=agent.call_outcome, summary=summary,
                   escalated_to_human=agent.escalated, language_detected=agent.language)
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
        (Ollama ⇄ Groq/OpenAI)                (Part 1)
```

| Module | Plan task | What it does |
|---|---|---|
| `router.py` | 2.2, 2.3 | `ModelRouter`: local model under a latency cap, cloud on timeout/error, Hindi → cloud, circuit breaker after repeated local failures |
| `tools.py` | 2.4, 2.9 | 11 tools over the service contract; caller phone and hospital come from the call, never the LLM |
| `graph.py` | 2.5, 2.8 | LangGraph state machine with per-call memory and a tool-round limit |
| `prompts.py` | 2.6 | System prompt from the database: hospital, departments, doctors, today's free slots, call rules |
| `language.py` | 2.7 | Hindi/English detection (Devanagari, Hinglish, STT hint; Whisper's `ur` → `hi`) |
| `guardrails.py` | 2.10 | Blocks medical advice and booking/cancel/token claims not backed by a tool result; strips IDs; trims length |
| `events.py` | — | Records tool results for the summary, call outcome and grounding checks |
| `agent.py` | 2.11, 2.12 | `MedNexaAgent`: greeting, turns, summary, outcome, failure handling |
| `evals.py` | 2.13 | Scenario runner against a real model |

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
| `CLOUD_PROVIDER` / `CLOUD_MODEL` | `groq` / `llama-3.3-70b-versatile` | Cloud model; only used when `GROQ_API_KEY` or `OPENAI_API_KEY` is set. Check the provider's current model list |
| `MAX_LATENCY_SECONDS` | `3` | Local calls slower than this fall back to cloud |
| `HINDI_PREFERS_CLOUD` | `true` | Send Hindi turns to the cloud model when available |
| `CIRCUIT_FAILURE_THRESHOLD` / `CIRCUIT_OPEN_SECONDS` | `3` / `300` | Skip local after repeated failures |
| `MAX_TOOL_ROUNDS` | `6` | Tool round trips per caller turn before forcing an answer |
| `MAX_RESPONSE_CHARS` | `600` | Spoken reply length cap |

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
