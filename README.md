# AI-Powered Workflow Automation Platform

An end-to-end automation system that converts natural-language requests into executable workflows using AI + n8n.

This implementation includes a real-world **Incident Triage & RCA** demo flow (payment failure investigation), with dashboard/email delivery, traceability, retries, and idempotency.

## Key Features

- Natural-language automation intake from UI/API/webhook
- AI instruction parsing into validated workflow schema
- n8n workflow execution with structured response handling
- Incident-style output: severity, affected service, root cause, actions
- Result delivery via dashboard and email
- Execution history + trace IDs for auditability
- Reliability controls: retries, idempotency keys, correlation IDs
- Security baseline: API key protection + API rate limiting
- Docker deployment and GitHub Actions CI

## Architecture Modules

1. User Request Module: `POST /api/requests`, `POST /api/webhook/intake`, dashboard form
2. AI Task Understanding: `AIInterpreterService`
3. Workflow Generator: `WorkflowGeneratorService`
4. Execution Engine: `ExecutionEngineService` (n8n webhook + retry/backoff)
5. Result Delivery: `ResultDeliveryService` (email/dashboard/slack)
6. Logging Module: SQLite-backed `WorkflowRun` + `IdempotencyRecord`
7. Dashboard Module: `/dashboard`
8. Deployment: Docker + Compose (`backend` + `n8n`)
9. CI/CD: `.github/workflows/ci-cd.yml`

## Tech Stack

- FastAPI, Uvicorn
- SQLAlchemy, SQLite
- Pydantic
- Jinja2
- n8n
- Docker, Docker Compose
- GitHub Actions

## Real-World Demo Scenario

Input request:

`Investigate payment failures and send incident report to email and dashboard`

Output includes:

- `severity` (P1/P2/P3)
- `affected_service`
- `probable_root_cause`
- `recommended_actions`
- `priority_message`
- `correlation_id`
- `attempt` (retry metadata)

## Local Setup (Windows)

```cmd
cd /d "c:\AI-powered workflow Automation"
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install -r backend\requirements.txt
copy .env.example .env
```

Start backend:

```cmd
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Start n8n:

```cmd
docker compose up -d n8n
```

Open:

- Dashboard: `http://127.0.0.1:8000/dashboard`
- API docs: `http://127.0.0.1:8000/docs`
- n8n: `http://127.0.0.1:5678`

## Environment Variables

Use `.env.example` as template.

Important controls:

- `API_ACCESS_KEY` (optional API auth)
- `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`
- `N8N_RETRY_ATTEMPTS`, `N8N_RETRY_BACKOFF_SECONDS`
- SMTP settings for email delivery (`SMTP_*`, `EMAIL_FROM`)

## API Security and Reliability Headers

- `X-API-Key` (if `API_ACCESS_KEY` is configured)
- `X-Idempotency-Key` (deduplicate repeated client retries)
- `X-Correlation-ID` (trace request across backend + n8n)

## Quick Test

```cmd
python -m pytest backend\tests -q
```

PowerShell API test:

```powershell
$body = @{
  user_id = "demo-user@example.com"
  request_text = "Investigate payment failures and send incident report to dashboard"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/requests" -Method Post -ContentType "application/json" -Body $body
```

## Interview Talking Points

- Built modular AI-to-automation orchestration backend
- Implemented production-minded controls (rate limiting, idempotency, retry, correlation IDs)
- Designed dynamic incident triage workflow in n8n with conditional branching
- Delivered full-stack execution visibility through dashboard + logs

## Important Security Note

Never commit real secrets. Keep `.env` local only and rotate any leaked keys immediately.
