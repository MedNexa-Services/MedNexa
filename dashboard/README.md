# MedNexa Admin Dashboard 🏥

Modern, high-performance Hospital Administration & AI Telephony Management Platform built with **Next.js 16 (App Router)**, **TypeScript**, **Tailwind CSS**, and **shadcn/ui**.

MedNexa empowers hospital staff, doctors, and receptionists to monitor live appointments, manage doctor rosters, configure schedule overrides, inspect AI phone call transcripts, and maintain the AI voice agent's knowledge base.

---

## ⚡ Tech Stack

- **Framework**: [Next.js 16](https://nextjs.org/) (App Router with Webpack)
- **Language**: TypeScript (Strict Mode)
- **Styling**: Tailwind CSS & Base UI / shadcn/ui
- **Icons**: [Lucide React](https://lucide.dev/)
- **Charts & Visualizations**: [Recharts](https://recharts.org/)
- **Notifications**: [Sonner](https://sonner.emilkowal.ski/)
- **API Client**: Axios with fully typed OpenAPI TypeScript contracts
- **Theme**: Light & Dark mode support via `next-themes`

---

## 📋 Prerequisites

Before running the dashboard, ensure you have:

1. **Node.js**: v18.17+ or v20+ (`node -v`)
2. **Package Manager**: npm v9+ or pnpm
3. **MedNexa FastAPI Backend**: Running on `http://127.0.0.1:8000` (PostgreSQL on port `5434`).
   - Verify with: `curl http://127.0.0.1:8000/docs`

---

## 🚀 Quick Start

### 1. Configure Environment Variables

Copy the example environment configuration into `.env.local`:

```bash
cp .env.example .env.local
```

Default configuration in `.env.local`:
```env
# Point to your MedNexa FastAPI backend API root
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXTAUTH_SECRET=change-me-in-production
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Launch Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

> **Staff Demo Credentials**:
> - Email: `admin@hospital.com`
> - Password: `admin123`

---

## 🧭 Dashboard Navigation & Modules

| Route | Module | Purpose |
|---|---|---|
| `/dashboard` | **Home Overview** | Today's appointment counters, real-time consultation feed, and doctors on duty. |
| `/doctors` | **Doctor Roster** | Manage practitioners, weekly recurring availability, slot limits, and active status. |
| `/doctors/[id]` | **Doctor Profile** | Edit practitioner qualification, department, bio, and launch schedule manager. |
| `/doctors/[id]/schedule` | **Schedule Overrides** | Interactive month calendar for date-specific leaves and modified clinic hours. |
| `/appointments` | **Appointments** | Filterable consultation table by date/doctor/status with 3-step booking wizard. |
| `/appointments/[id]` | **Appointment Details** | Full audit trail, patient identity, and staff reschedule/cancellation actions. |
| `/patients` | **Patient Directory** | Phone-normalized patient lookups and demographic profiles. |
| `/patients/[id]` | **Patient History** | Complete historical timeline of all past and upcoming consultations. |
| `/hospital-info` | **AI Knowledge Base** | Add, edit, and toggle hospital FAQs used by the AI voice agent. |
| `/call-logs` | **Telephony Logs** | Real-time call sessions, duration, and human emergency escalation markers. |
| `/call-logs/[id]` | **Transcript Viewer** | Turn-by-turn dialogue inspection and tool invocation logs. |
| `/analytics` | **Visual Analytics** | Recharts graphs for weekday volume, status distribution, and peak hours. |
| `/settings` | **Hospital Profile** | Operating hours, timezone (Asia/Kolkata), and AI multilingual voice settings. |

---

## 🐳 Docker Deployment

A multi-stage `Dockerfile` is provided for containerized deployments:

```bash
# Build production Docker image
docker build -t mednexa-dashboard:latest .

# Run container on port 3000
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://backend:8000/api/v1 mednexa-dashboard:latest
```

---

## 🛠️ Verification & Quality Checks

Run the TypeScript typecheck:
```bash
npm run build
```
*Expected: 0 TypeScript errors, all routes compiled cleanly.*
