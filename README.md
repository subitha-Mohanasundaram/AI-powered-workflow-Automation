

# 🤖 AI-Powered Workflow Automation Platform

### *Production-grade Orchestration, Natural Language Automation, and Real-Time Incident Triage*

[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#-quick-start-docker)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](http://localhost:8000/docs)
[![n8n](https://img.shields.io/badge/n8n-FF6D5A?style=for-the-badge&logo=n8n&logoColor=white)](#-n8n-workflow-automation)
[![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)](#-services-and-ports)

---

[Key Capabilities](#-key-capabilities) •
[Architecture](#-architecture) •
[Services & Ports](#-services-and-ports) •
[Quick Start](#-quick-start-docker) •
[API Reference](#-api-reference) •
[Incident Stack](#-incident-detection-stack)

</div>

<br />

## 🌟 Executive Summary

This platform combines a **FastAPI backend**, **n8n workflow orchestration**, **GPT-4o-mini natural language interpretation**, and an automated **incident triage engine**. It bridges human intent with scheduled execution, encrypted secret storage, and real-time observability across Prometheus, Loki, and Grafana.

## Security Notes

- **Never commit `.env`** — it is listed in `.gitignore`
- `SECRET_KEY` must be a strong random string in production (used for Fernet encryption of stored credentials)
- `API_ACCESS_KEY` should be set in production to restrict API access
- All sensitive user data (SMTP credentials, API keys, Slack webhooks) is encrypted at rest using `cryptography` (Fernet)
- Input validation and prompt-injection prevention are applied on all text fields

    🗣️ Plain-English Request ──┐
                              ├──► 🧠 GPT-4o-mini Interpreter ──► ⚡ n8n Execution Engine ──► 📊 Dashboards & Alerts
   📈 Simulated Metrics/Logs ─┘

---

## ✨ Key Capabilities

<details open>
<summary><b>1. 💬 Natural Language Automation</b></summary>
Submit plain-English text prompts; the AI interprets the request, maps parameters, and dispatches structured n8n execution pipelines automatically.
</details>

<details>
<summary><b>2. 🚨 Real-Time Incident Triage</b></summary>
Simulates system metric spikes, collects logs via Loki/Promtail, and leverages n8n workflows to auto-detect P1–P3 issues and infer root causes.
</details>

<details>
<summary><b>3. 🔒 End-to-End Encryption & Security</b></summary>
Sensitive user credentials (SMTP details, API keys, Slack Webhooks) are encrypted at rest using Fernet. Features replay-safe `X-Idempotency-Key` headers and per-user rate limiting.
</details>

<details>
<summary><b>4. ⏰ Flexible Scheduling Engine</b></summary>
Built-in support for recurring jobs (`every_day`, `every_hour`, cron strings) managed directly via APScheduler.
</details>

<details>
<summary><b>5. 📊 Full-Stack Observability</b></summary>
Pre-configured Prometheus metrics scraping, Loki log aggregation, and customized Grafana visual dashboards.
</details>

---

## 🛠️ Architecture Overview

User / Client
│
▼
FastAPI Backend (Port 8000)
├── 🧠 AI Interpreter (OpenAI GPT-4o-mini)
├── 📐 Workflow Generator & APScheduler
├── ⚡ Execution Engine ──► n8n Orchestrator (Port 5678)
├── 🔒 Fernet Profile Encryption & DB (SQLite)
└── 📡 Delivery Engine (Email / Slack / Dashboard)

Incident Detection Stack
├── 🎲 Metrics & Log Simulator ──► Prometheus (Port 9090) + Loki (Port 3100)
├── 🔍 n8n Investigation Workflow
├── 🟢 Node.js Incident API (Port 8001) + MongoDB
└── 💻 React Incident Dashboard (Port 3000)

Monitoring & Observability
└── 📊 Grafana Dashboard (Port 3001)
---

## 🔌 Services and Ports

| Service | Local Endpoint | Auth / Credentials | Description |
| :--- | :--- | :--- | :--- |
| **FastAPI Backend** | `http://localhost:8000` | `X-API-Key` Header | Core automation API |
| **Swagger Docs** | `http://localhost:8000/docs` | *None* | Interactive API playground |
| **Incident API** | `http://localhost:8001` | *None* | Express/Node incident store |
| **React Dashboard** | `http://localhost:3000` | *None* | Incident management UI |
| **n8n Orchestrator**| `http://localhost:5678` | `admin` / `admin` | Workflow engine UI |
| **Grafana** | `http://localhost:3001` | `admin` / `admin` | Metrics & log viewer |
| **Prometheus** | `http://localhost:9090` | *None* | Time-series metrics engine |
| **Loki Logs** | `http://localhost:3100` | *None* | Centralized log aggregator |
| **Metrics Simulator**| `http://localhost:9000/metrics`| *None* | Simulated metric target |

---

## ⚡ Quick Start (Docker)

### 1️⃣ Clone & Configure Environment
```bash
copy .env.example .env
Edit your .env file to include your OpenAI API key and encryption secret:

Code snippet
AI_API_KEY=sk-...            # Your OpenAI API Key
SECRET_KEY=your-random-key  # Strong random string for Fernet encryption
2️⃣ Launch Full Stack
Bash
docker compose up --build
📖 API Reference
🏥 Health Probes
GET /health — Liveness check. Returns {"status":"ok"}.

GET /health/ready — Readiness probe (validates database connection).

🤖 Automation Requests
POST /api/requests — Submit a natural language request.

GET /api/runs — Fetch execution history (limit: 100).

GET /api/runs/{id} — Fetch single workflow execution details.

Sample Request Body (POST /api/requests):

JSON
{
  "user_id": "user@example.com",
  "request_text": "Fetch the weather for Chennai and send me a daily report"
}

⏰ Scheduled Workflows
POST /api/scheduled — Create a scheduled job.

GET /api/scheduled?user_id=... — List workflows for a user.

POST /api/scheduled/{id}/run — Trigger manual execution.

POST /api/scheduled/{id}/pause — Pause active schedule.

POST /api/scheduled/{id}/resume — Resume paused schedule.

Supported Schedules: every_day, every_hour, every_monday, every_weekday, every_30_minutes, every_6_hours, or custom cron strings (e.g., cron:0 9 * * 1).

⚙️ Environment Configuration (.env)
┌───────────────────────────┬───────────────────────────────────────────────────────┬─────────────────────────┐
│ Variable                  │ Purpose                                               │ Default                 │
├───────────────────────────┼───────────────────────────────────────────────────────┼─────────────────────────┤
│ APP_NAME                  │ Application display title                             │ AI Workflow Automation  │
│ APP_ENV                   │ Mode (development / production)                       │ development             │
│ SECRET_KEY                │ Encryption key for confidential user profiles        │ (Required)              │
│ DATABASE_URL              │ Relational database connection string                 │ sqlite:///./automation  │
│ AI_API_KEY                │ OpenAI service key                                    │ (Required)              │
│ AI_MODEL                  │ Primary LLM selection                                 │ gpt-4o-mini             │
│ RATE_LIMIT_REQUESTS       │ Window-based request throttling limit                 │ 100                     │
│ N8N_WEBHOOK_URL           │ Endpoint target for dispatched workflows              │ Set in docker-compose   │
└───────────────────────────┴───────────────────────────────────────────────────────┴─────────────────────────┘
📂 Project Structure
Code snippet
.
├── 📁 backend/                 # FastAPI server, AI services, and APScheduler
│   ├── 📁 app/
│   │   ├── 📄 main.py          # Entry point & global middleware
│   │   ├── 📁 routers/         # API routes (Requests, Scheduler, AI, LeetCode)
│   │   └── 📁 services/        # Logic (AI parser, Fernet encryption, Execution)
│   └── 📁 tests/            # Pytest test suite
├── 📁 incident-api/            # Express.js incident storage server
├── 📁 incident-dashboard/      # React + Vite visualization interface
├── 📁 simulator/               # Metrics and log spike generator
├── 📁 monitoring/              # Prometheus, Loki, Promtail & Grafana configs
├── 📁 n8n-workflows/           # Pre-built importable n8n workflow JSONs
├── 📁 scripts/                 # Utility scripts & verification suite
└── 📄 docker-compose.yml       # Container orchestration spec
🤝 Demo & Testing Scripts
Run test scripts from your terminal to verify pipeline components:

Bash
# Test FastAPI automation pipeline
python scripts/demo_request_fastapi.py

# Verify health status across all running container services
python scripts/verify_all.py

# Run unit tests with coverage report
cd backend && pytest tests/ -v --cov=app
