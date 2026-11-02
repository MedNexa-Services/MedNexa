# MedNexa dashboard

The staff side of MedNexa: today's token queues, appointments, doctors and their
schedules, patients, the answers the receptionist gives callers, call transcripts and
analytics. Next.js 16 (App Router), TypeScript, Tailwind CSS and Base UI components.

## Running it

It needs the backend running (see `../backend/README.md`).

```bash
cp .env.example .env.local     # BACKEND_URL, and TELEPHONY_URL for the phone-line status
npm install
npm run dev                    # http://localhost:3000
```

Sign in with the staff account configured on the backend (`MEDNEXA_ADMIN_EMAIL` /
`MEDNEXA_ADMIN_PASSWORD`). On a fresh install the dashboard first asks for the hospital's
details, then for its doctors.

## How it talks to the API

The browser only talks to the dashboard. The dashboard server signs in on the browser's
behalf, keeps the backend's token in an httpOnly cookie, and forwards `/api/backend/*` to
`BACKEND_URL/api/v1/*` with it, so page JavaScript never sees the token and staff machines
don't need to reach the API. The cookie is `Secure` by default; if the dashboard is served
over plain HTTP on a hospital network, set `AUTH_COOKIE_SECURE=false` (HTTPS is better).

## Pages

| Route | What it shows |
|---|---|
| `/dashboard` | Today: each doctor's token queue, who is next, open slots |
| `/appointments` | All appointments, searchable by patient name, phone or token; booking |
| `/doctors` | Doctors, their weekly hours, leave and changed hours (`/doctors/[id]/schedule`) |
| `/patients` | Patients and their visit history |
| `/hospital-info` | Answers the receptionist gives callers (timings, parking, fees, ...) |
| `/call-logs` | Calls answered by the receptionist, with transcripts and hand-overs to staff |
| `/analytics` | Busiest days and hours, appointments per doctor, call figures |
| `/settings` | Hospital details, OPD hours, notes for the receptionist, phone line setup |

## Checks

```bash
npm run lint
npx tsc --noEmit
npm run build
```

The same checks run in CI (`.github/workflows/dashboard.yml`).
