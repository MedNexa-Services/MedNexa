# MedNexa Backend (Part 1)

Database, service layer and REST API for MedNexa. The AI agent (Part 2) calls the
service layer directly; the admin dashboard (Part 4) and call pipeline (Part 3) use
the REST API.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy 2.1 (async) · asyncpg · Alembic · PostgreSQL 16 · uv

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cd backend
uv sync                                               # install dependencies into .venv
docker compose -f docker-compose.dev.yml up -d --wait # Postgres 16 on localhost:5434
uv run alembic upgrade head                           # create the schema
uv run python -m scripts.seed                         # sample hospital, doctors, bookings
uv run uvicorn app.main:app --reload                  # http://localhost:8000/docs
```

The dev container also creates a `mednexa_test` database for the test suite. To
change settings, copy `.env.example` to `.env` (all variables use the `MEDNEXA_`
prefix).

## Common commands

| Task | Command |
|---|---|
| Run tests (needs the dev container) | `uv run pytest` |
| Tests with coverage (fails under 80%) | `uv run pytest --cov` |
| Lint / format | `uv run ruff check .` · `uv run ruff format .` |
| Type check | `uv run mypy app` |
| New migration after a model change | `uv run alembic revision --autogenerate -m "describe change"` |
| Check models and migrations agree | `uv run alembic check` |
| Reset sample data | `uv run python -m scripts.seed --reset` |

## CI

`.github/workflows/backend.yml` runs only on pushes and pull requests that change
files under `backend/`; changes elsewhere in the repo don't trigger it. It can
also be started manually from the Actions tab:

- **Lint, format & types:** ruff check, ruff format --check, mypy
- **Migrations & tests:** against a Postgres 16 service container: `alembic upgrade
  head`, `alembic check` (models and migrations agree), the seed script, then
  `pytest --cov` (fails under 80%); the coverage report is uploaded as an artifact

Run the same checks locally before pushing:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy app scripts && uv run pytest --cov
```

## Layout

```
app/
├── main.py              app factory, CORS, error handlers
├── config.py            settings (pydantic-settings, MEDNEXA_ prefix)
├── database.py          async engine, session factory, get_db
├── models/              SQLAlchemy models + enums
├── schemas/             Pydantic DTOs (request/response)
├── services/            business logic: the ONLY layer that touches the DB
│   └── contracts.py     the functions Part 2's agent tools wrap
├── api/
│   ├── deps.py          DB session, pagination, require_staff auth hook
│   ├── errors.py        domain exception -> HTTP mapping
│   └── v1/              route modules
└── core/                exceptions, phone/name normalization, time helpers
alembic/                 migrations
scripts/seed.py          sample data
tests/                   pytest suite against real Postgres
```

## Business rules

| Rule | Where it's enforced |
|---|---|
| One BOOKED appointment per doctor slot | Partial unique index `WHERE status = 'BOOKED'` + booking service |
| Cancelled/rescheduled slots can be rebooked | Uniqueness only applies to BOOKED rows |
| Same phone + different name = different patient | Patient identity is `(hospital, phone, normalized name)` |
| Same patient, same doctor, same time is rejected | `DuplicateBooking` |
| Daily cap per doctor | Checked under the doctor row lock |
| No double booking under concurrent calls | `SELECT … FOR UPDATE` on the doctor row; tested with 20 parallel bookings |
| Token numbers | Per doctor per day, sequential, never reused |
| Doctor schedule | Doctor fields = weekly template; `schedule` rows override single dates |
| Time | Appointment date/time are hospital-local; "today" and "already passed" use `hospital.timezone` |
| Phone numbers | Stored as `+<country><number>`; `98765 43210`, `098765-43210` and `+91 98765 43210` are the same number |

## For Part 2 (AI agent)

Import only from `app.services.contracts`:

```python
from app.services import contracts

slots = await contracts.get_available_slots(db, doctor_id, date(2026, 11, 2))
confirmation = await contracts.book_appointment(db, BookingRequest(...))
await contracts.cancel_appointment(db, appointment_id, caller_phone=state.caller_phone)
```

- Each function takes an `AsyncSession` first (use `app.database.SessionFactory`).
- Take `hospital_id` and `caller_phone` from the call state, never from the LLM.
- Expected failures raise `app.core.exceptions.DomainError` subclasses with a stable
  `code` (`slot_unavailable`, `daily_cap_reached`, `not_owner`, …) and a readable
  `message`. Catch them and let the LLM explain them to the caller.
- Write functions commit their own transaction.
- Caller cancel/reschedule check that `caller_phone` owns the appointment.

## For Part 3 (call pipeline)

Persist calls through the REST API: `POST /api/v1/calls` at the start,
`POST /api/v1/calls/{id}/logs` for each turn or tool call, and
`POST /api/v1/calls/{id}/end` with the outcome.

## For Part 4 (dashboard)

The OpenAPI spec is at `/openapi.json` (interactive docs at `/docs`); generate a
typed client from it. Lists return `{items, total, limit, offset}` and take
`limit`/`offset`. Errors return `{"error": {"code", "message"}}`.
Staff cancel/reschedule (`POST /appointments/{id}/cancel|reschedule`) skip the
phone-ownership check.

## Authentication

Every `/api/v1` route except `/health` and `/auth/login` needs a staff token
(`Authorization: Bearer <jwt>`), obtained from `POST /api/v1/auth/login`.

- The API **refuses to start** until `MEDNEXA_JWT_SECRET` (32+ characters),
  `MEDNEXA_ADMIN_EMAIL` and `MEDNEXA_ADMIN_PASSWORD` are set; there are no default
  credentials or keys. For local work without login set `MEDNEXA_AUTH_ENABLED=false`.
- `MEDNEXA_ADMIN_PASSWORD` may be a PBKDF2 hash: `uv run python -m app.core.security`.
- Login is throttled: 5 wrong passwords per account (30 per address) per 5 minutes
  return 429. The limiter is per process (use Redis if you run several workers).
- The telephony service authenticates with `MEDNEXA_SERVICE_API_KEY`, which works on
  the `/calls` routes only and opens nothing else.

## For Part 5 (DevOps)

- Authentication is implemented (see above); every route except `/api/v1/health` and
  `/api/v1/auth/login` depends on `require_staff`.
- Health check: `GET /api/v1/health` returns 503 if the database is unreachable.
- Run `alembic upgrade head` before starting the API in each deployment.
