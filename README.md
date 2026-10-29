# MedNexa — Voice-Enabled Agentic AI Hospital Receptionist 🏥

MedNexa is an autonomous, bilingual (English & Hindi) voice-enabled AI hospital receptionist system. It handles inbound patient calls, provides hospital information, books and cancels doctor appointments with conflict-free scheduling, and provides hospital staff with a modern Next.js admin dashboard.

---

## 🏗️ System Architecture

```
                                  ┌──────────────────────────┐
                                  │   Caller (Phone/Twilio)   │
                                  └─────────────┬────────────┘
                                                │ SIP / WebSockets
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MedNexa Platform (Dockerized)                                                          │
│                                                                                        │
│   ┌─────────────────────┐       ┌──────────────────────┐       ┌───────────────────┐  │
│   │ Telephony Gateway   │ ────▶ │ AI Agent Core        │ ────▶ │ Database Layer    │  │
│   │ (Twilio / VAD /     │ ◀──── │ (LangGraph + Tools   │ ◀──── │ (PostgreSQL 16)   │  │
│   │  Whisper STT / TTS) │       │  ModelRouter:        │       │                   │  │
│   │  Port: 8001         │       │  Ollama / Groq / OAI)│       │  Port: 5434 (local)│ │
│   └─────────────────────┘       └──────────────────────┘       └─────────▲─────────┘  │
│                                                                          │            │
│   ┌─────────────────────┐                                                │            │
│   │ Next.js Dashboard   │ ───────────────────────────────────────────────┤            │
│   │ (Port: 3001)        │   same-origin gateway, JWT in httpOnly cookie  │            │
│   └─────────────────────┘              REST API (FastAPI), JWT auth      │            │
│                                        Port: 8000 (localhost only)       │            │
│                                 ┌──────────────────────┐                 │            │
│                                 │ FastAPI Backend API  │ ────────────────┘            │
│                                 └──────────────────────┘                              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Services and Port Mapping

| Service | Technology | Port (Host) | Description |
|---|---|---|---|
| **Backend API** | FastAPI / Python 3.11 | `127.0.0.1:8000` | REST API, business logic, JWT auth. Local access only; staff use the dashboard |
| **Admin Dashboard** | Next.js 16 / TypeScript | `3001` | Staff portal. Its server signs in to the API and proxies browser requests to it |
| **Telephony Gateway** | FastAPI / Silero / Whisper | `8001` | Audio streaming, VAD, STT, Edge/Piper TTS, Twilio. Put an HTTPS proxy in front |
| **Database** | PostgreSQL 16 | `127.0.0.1:5434` | Appointments, doctors, schedules, call logs (local access only) |
| **Local LLM** | Ollama | internal | Local inference (`llama3.1:8b`); no published port because Ollama has no authentication |


---

## 🚀 Quick Start (Docker Deployment - Part 5)

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) v2+
- Git

### 2. Configure Environment
```bash
cp .env.example .env
```
Fill in every value marked **REQUIRED** (generate random secrets with `openssl rand -hex 32`):
`POSTGRES_PASSWORD`, `MEDNEXA_JWT_SECRET`, `MEDNEXA_SERVICE_API_KEY`, `MEDNEXA_ADMIN_EMAIL`
and `MEDNEXA_ADMIN_PASSWORD`. There are **no default credentials or keys**: `docker compose`
refuses to start until they are set, and so does the API. Cloud-fallback keys such as
`MEDNEXA_AGENT_GROQ_API_KEY` are optional.

### 3. Start the Stack
```bash
docker compose up --build -d
```
Compose starts PostgreSQL, applies the migrations (a one-off `migration` container), then
starts the API (waits until healthy), the dashboard and the telephony gateway. The sample
data is **not** loaded automatically; to try the system with a demo hospital:
```bash
docker compose --profile demo run --rm seed
```

### 4. Finish Setup
1. **Sign in** at [http://localhost:3001](http://localhost:3001) with `MEDNEXA_ADMIN_EMAIL` / `MEDNEXA_ADMIN_PASSWORD`.
   Over plain HTTP from another machine, set `AUTH_COOKIE_SECURE=false` in `.env`
   (HTTPS through a reverse proxy is strongly preferred).
2. **Telephony needs a hospital:** create it in the dashboard (or run the demo seed), copy its
   id into `MEDNEXA_TEL_HOSPITAL_ID` in `.env`, then `docker compose up -d telephony`.
   `http://localhost:8001/health` reports `hospital_configured` and `backend_connected`.
3. **Local model (optional):** `docker compose exec ollama ollama pull llama3.1:8b`.
4. **Twilio:** set `MEDNEXA_TEL_PUBLIC_URL` and the Twilio credentials in `.env`; with an auth
   token set, the webhook only accepts requests signed by Twilio.

Useful addresses: dashboard `http://localhost:3001`, API docs `http://localhost:8000/docs`,
API health `http://localhost:8000/api/v1/health`, telephony health `http://localhost:8001/health`.

---

## 🔐 Security & Authentication (Task 5.3)

- **One place checks credentials: the backend.** `POST /api/v1/auth/login` verifies the staff
  account from `MEDNEXA_ADMIN_EMAIL` / `MEDNEXA_ADMIN_PASSWORD` (plain or a PBKDF2 hash from
  `python -m app.core.security`) and returns an HS256 JWT. Every other route needs it, except
  `/api/v1/health`.
- **The dashboard never exposes the token.** Its server signs in on the browser's behalf, keeps the
  JWT in an `httpOnly` cookie, and forwards browser requests (`/api/backend/*`) to the API with it.
  Cross-site writes are refused.
- **No defaults.** The API refuses to start without a 32+ character `MEDNEXA_JWT_SECRET` and the
  admin credentials. Sign-in is throttled (5 wrong passwords per account per 5 minutes).
- **Telephony uses a separate service key** (`MEDNEXA_SERVICE_API_KEY`) that is accepted on the
  `/calls` routes only.
- **Network exposure:** only the dashboard (3001) and the telephony webhook (8001) listen on all
  interfaces; the API and database are bound to localhost and Ollama is internal.
- `X-Correlation-ID` is echoed (if it is short and uses safe characters) for tracing across logs.

---

## 💾 Database Backup & Disaster Recovery (Task 5.12)

Automated backup and restore scripts are located in `scripts/`:

### Creating a Backup
- **Linux / macOS**:
  ```bash
  ./scripts/backup.sh
  ```
- **Windows (PowerShell)**:
  ```powershell
  .\scripts\backup.ps1
  ```
Backups are saved to `./backups/mednexa_backup_<timestamp>.sql.gz` (readable by you only), made
inside the database container and verified before they replace anything; a failed run leaves
existing backups untouched, and backups older than 7 days (`RETENTION_DAYS`) are pruned only
after a successful one. They contain patient data: copy them off the machine and encrypt them
(e.g. `gpg --symmetric`).

### Restoring from Backup
Stop the services that use the database first (`docker compose stop api telephony dashboard`) and
start them again afterwards. A restore replaces the database contents in a single transaction: if
anything fails, nothing changes.

- **Linux / macOS**:
  ```bash
  ./scripts/restore.sh ./backups/mednexa_backup_<timestamp>.sql.gz      # add -y to skip the prompt
  ```
- **Windows (PowerShell)**:
  ```powershell
  .\scripts\restore.ps1 -BackupFile .\backups\mednexa_backup_<timestamp>.sql.gz   # add -Yes to skip the prompt
  ```

---

## 🛠️ Local Development (Without Docker)

### Backend (Part 1)
```bash
cd backend
uv sync
# set MEDNEXA_JWT_SECRET, MEDNEXA_ADMIN_EMAIL and MEDNEXA_ADMIN_PASSWORD (see backend/.env.example),
# or MEDNEXA_AUTH_ENABLED=false for local work without login
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --port 8000 --reload
```

### AI Agent (Part 2)
```bash
cd agent
uv sync
uv run mednexa-chat
```

### Voice / Telephony (Part 3)
```bash
cd telephony
uv sync
uv run uvicorn telephony.main:app --port 8001 --reload
```

### Admin Dashboard (Part 4)
```bash
cd dashboard
npm install
BACKEND_URL=http://localhost:8000 npm run dev
```

---

## 🧪 CI/CD Automation

Continuous Integration workflows run via GitHub Actions on every pull request and push:
- **`backend.yml`**: Ruff linting, formatting, mypy static analysis, Alembic migration verification, and Postgres pytest suite.
- **`agent.yml`**: Agent harness, LangGraph evaluation, tool-calling tests.
- **`dashboard.yml`**: ESLint, TypeScript compilation (`tsc --noEmit`), Next.js production build.
- **`telephony.yml`**: ruff and the voice pipeline tests (Whisper, Silero and TTS are mocked).
- **`docker.yml`**: validates `docker-compose.yml`, lints the backup scripts, builds the API and dashboard images and starts the stack to check it comes up healthy.

---

## 📄 License
MedNexa is proprietary medical receptionist software designed for high-concurrency hospital operations.
