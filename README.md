# AI-Powered Workflow Automation Platform

A full-stack, production-style automation platform that combines a **FastAPI backend**, **n8n workflow orchestration**, **AI-powered natural language interpretation**, and an **incident detection system** with real-time monitoring.

---

## Features

- **Natural Language Automation** — Submit plain-English requests; the AI (GPT-4o-mini) interprets and dispatches structured workflows automatically
- **Scheduled Workflows** — Create recurring workflows (daily, hourly, cron) that run automatically with APScheduler
- **Incident Detection** — Real-time metrics simulation, Prometheus scraping, Loki log aggregation, and automated n8n triage workflows
- **Multi-Channel Delivery** — Results delivered via Dashboard, Email (SMTP), or Slack webhook
- **Encrypted User Profiles** — Confidential settings (API keys, SMTP credentials, Slack webhooks) stored encrypted at rest using Fernet
- **Idempotent Requests** — Replay-safe submissions via `X-Idempotency-Key` header
- **Rate Limiting** — Per-user request throttling middleware
- **LeetCode Tracker** — Track and report student LeetCode progress by batch
- **Full Observability** — Prometheus metrics, Loki + Promtail log aggregation, Grafana dashboards

---

## Architecture

```
User / Client
     |
     v
FastAPI Backend (port 8000)
  ├── AI Interpreter (OpenAI GPT-4o-mini)
  ├── Workflow Generator
  ├── Execution Engine → n8n (port 5678)
  ├── Result Delivery (Email / Slack / Dashboard)
  ├── Scheduler (APScheduler)
  └── SQLite Database

Incident Detection Stack
  ├── Metrics Simulator → Prometheus (port 9090)
  ├── Log Generator → Loki + Promtail (port 3100)
  ├── n8n Investigation Workflow
  ├── Node.js Incident API (port 8001) + MongoDB
  └── React Incident Dashboard (port 3000)

Monitoring
  └── Grafana (port 3001)
```

---

## Services and Ports

| Service                   | URL                          | Credentials       |
|---------------------------|------------------------------|-------------------|
| FastAPI Backend           | http://localhost:8000        | X-API-Key header  |
| FastAPI Docs (Swagger)    | http://localhost:8000/docs   | —                 |
| Incident API (Express)    | http://localhost:8001        | —                 |
| Incident Dashboard (React)| http://localhost:3000        | —                 |
| n8n                       | http://localhost:5678        | admin / admin     |
| Prometheus                | http://localhost:9090        | —                 |
| Grafana                   | http://localhost:3001        | admin / admin     |
| Loki                      | http://localhost:3100        | —                 |
| Metrics Simulator         | http://localhost:9000/metrics| —                 |

---

## Quick Start (Docker)

```cmd
copy .env.example .env
```

Edit `.env` and set at minimum:

```env
AI_API_KEY=sk-...           # Your OpenAI API key
SECRET_KEY=your-random-key  # Strong random string for encryption
```

Then start the full stack:

```cmd
docker compose up --build
```

---

## Environment Configuration (`.env`)

| Variable                    | Description                                          | Default               |
|-----------------------------|------------------------------------------------------|-----------------------|
| `APP_NAME`                  | Application display name                             | AI Workflow Automation|
| `APP_ENV`                   | Environment (`development` / `production`)           | development           |
| `APP_PORT`                  | Backend port                                         | 8000                  |
| `SECRET_KEY`                | Fernet encryption key for confidential data          | *(must be set)*       |
| `DATABASE_URL`              | SQLAlchemy DB URL                                    | sqlite:///./automation.db |
| `API_ACCESS_KEY`            | Optional API key for all endpoints (blank = open)    | *(blank)*             |
| `RATE_LIMIT_REQUESTS`       | Max requests per window per user                     | 100                   |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate limit window size                               | 60                    |
| `AI_API_KEY`                | OpenAI API key                                       | *(required)*          |
| `AI_MODEL`                  | OpenAI model to use                                  | gpt-4o-mini           |
| `AI_TIMEOUT_SECONDS`        | Timeout for AI calls                                 | 30                    |
| `N8N_WEBHOOK_URL`           | Full n8n webhook URL for workflow execution          | *(set for Docker)*    |
| `SMTP_HOST`                 | SMTP server for email delivery                       | *(optional)*          |
| `SMTP_PORT`                 | SMTP port                                            | 587                   |
| `SMTP_USER`                 | SMTP username                                        | *(optional)*          |
| `SMTP_PASSWORD`             | SMTP password                                        | *(optional)*          |
| `SLACK_WEBHOOK_URL`         | Slack incoming webhook URL                           | *(optional)*          |

---

## FastAPI Backend — API Reference

### Health

| Method | Endpoint        | Description                        |
|--------|-----------------|------------------------------------|
| GET    | `/health`       | Liveness probe — returns `{"status":"ok"}` |
| GET    | `/health/ready` | Readiness probe — checks DB connection |

### Automation Requests

| Method | Endpoint               | Description                                      |
|--------|------------------------|--------------------------------------------------|
| POST   | `/api/requests`        | Submit a natural-language automation request     |
| POST   | `/api/webhook/intake`  | Webhook alias for `/api/requests`                |
| GET    | `/api/runs`            | List recent workflow runs (default limit: 100)   |
| GET    | `/api/runs/{id}`       | Get a single workflow run by ID                  |

**Request body for `POST /api/requests`:**
```json
{
  "user_id": "user@example.com",
  "request_text": "Fetch the weather for Chennai and send me a daily report"
}
```

**Optional headers:**
- `X-API-Key` — Required if `API_ACCESS_KEY` is set in `.env`
- `X-Idempotency-Key` — Prevent duplicate runs on retry
- `X-Correlation-ID` — Trace ID for distributed logging

### Scheduled Workflows

| Method | Endpoint                          | Description                         |
|--------|-----------------------------------|-------------------------------------|
| POST   | `/api/scheduled`                  | Create a new scheduled workflow     |
| GET    | `/api/scheduled?user_id=...`      | List all workflows for a user       |
| GET    | `/api/scheduled/{id}`             | Get a scheduled workflow            |
| PUT    | `/api/scheduled/{id}`             | Update schedule or config           |
| DELETE | `/api/scheduled/{id}`             | Delete (stop) a scheduled workflow  |
| POST   | `/api/scheduled/{id}/run`         | Trigger a manual run immediately    |
| POST   | `/api/scheduled/{id}/pause`       | Pause the schedule                  |
| POST   | `/api/scheduled/{id}/resume`      | Resume a paused workflow            |
| GET    | `/api/scheduled/{id}/history`     | Run history for a scheduled workflow|

**Supported schedule values:** `every_day`, `every_hour`, `every_monday`, `every_weekday`, `every_30_minutes`, `every_6_hours`, or a raw cron expression prefixed with `cron:` (e.g. `cron:0 9 * * 1`)

### User Profile

| Method | Endpoint               | Description                                    |
|--------|------------------------|------------------------------------------------|
| POST   | `/api/profile`         | Save user profile (sensitive fields encrypted) |
| GET    | `/api/profile/{user_id}` | Get profile (secrets are masked)             |

### LeetCode Tracker

Available under `/api/leetcode` — track student progress and generate batch reports. See `/docs` for full schema.

### Dashboard

Available under `/dashboard` — HTML dashboard for viewing workflow run history.

---

## n8n Workflow Automation

### Importing Workflows

1. Open n8n at `http://localhost:5678` (admin / admin)
2. Go to **Workflows → Import from File**
3. Import one or both:
   - `n8n-workflows/demo_incident_detection.json` — manual webhook trigger
   - `n8n-workflows/auto_detect_incident.json` — polls every minute for auto-detection

### Manual Trigger

```cmd
curl -X POST http://localhost:5678/webhook/incident-trigger ^
  -H "Content-Type: application/json" ^
  -d "{\"service_name\":\"payment-service\",\"reason\":\"demo\"}"
```

The workflow will:
1. Query Prometheus for error rate, latency, and DB utilization
2. Query Loki for recent error logs
3. Compute severity (P1 / P2 / P3) and infer root cause + actions
4. POST the incident report to the Incident API

---

## Incident Detection Stack

The simulator generates periodic spikes (configurable via `docker-compose.yml`):

```yaml
SPIKE_EVERY_SECONDS=120    # How often a spike occurs
SPIKE_DURATION_SECONDS=30  # How long each spike lasts
```

To force an immediate spike for demos, temporarily set:
```yaml
SPIKE_EVERY_SECONDS=30
SPIKE_DURATION_SECONDS=20
```

Then restart: `docker compose up --build`

---

## Demo Scripts

```cmd
# Trigger an automation request via the FastAPI backend
python scripts\demo_request_fastapi.py

# Trigger via n8n webhook
python scripts\demo_request.py

# Check current workflow run and scheduled workflow statuses in the DB
python scripts\check_status.py

# Verify all services are healthy
python scripts\verify_all.py

# Test LeetCode API endpoints
python scripts\test_leetcode_api.py
```

---

## Running Tests

```cmd
cd backend
pytest tests/ -v --cov=app
```

---

## Project Structure

```
.
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           # App entry point, middleware, routers
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── config.py         # Settings from environment
│   │   ├── security.py       # API key enforcement
│   │   ├── rate_limit.py     # Per-user rate limiting middleware
│   │   ├── routers/          # Route handlers (requests, scheduled, ai, health, leetcode, dashboard)
│   │   └── services/         # Business logic (ai, scheduler, execution, delivery, encryption)
│   ├── tests/                # Pytest test suite
│   └── requirements.txt
├── incident-api/             # Node.js/Express incident storage API
├── incident-dashboard/       # React/Vite incident visualization dashboard
├── simulator/                # Python metrics + log spike simulator
├── monitoring/               # Prometheus, Loki, Promtail, Grafana configs
├── n8n-workflows/            # Importable n8n workflow JSON files
├── scripts/                  # Utility and demo scripts
├── docker-compose.yml        # Full stack orchestration
└── .env.example              # Environment variable template
```

---

## Security Notes

- **Never commit `.env`** — it is listed in `.gitignore`
- `SECRET_KEY` must be a strong random string in production (used for Fernet encryption of stored credentials)
- `API_ACCESS_KEY` should be set in production to restrict API access
- All sensitive user data (SMTP credentials, API keys, Slack webhooks) is encrypted at rest using `cryptography` (Fernet)
- Input validation and prompt-injection prevention are applied on all text fields
