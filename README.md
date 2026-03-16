# AI-Powered Incident Detection and Automated Investigation Platform

A production-style demo system that:

1. Simulates real incidents (error spikes, latency spikes, DB overload)
2. Stores metrics in Prometheus and logs in Loki
3. Uses n8n to automate investigation and generate an incident report
4. Stores incident reports in MongoDB via a Node.js/Express API
5. Visualizes incidents in a React dashboard (active incidents + timeline)

## Architecture

```
Metrics Simulator + Log Generator
          |                         (logs)
          | (metrics)                 |
          v                           v
     Prometheus                   Loki + Promtail
          \                         /
           \                       /
            v                     v
                 n8n Investigation Workflow
                           |
                           v
                 Node.js Incident API (Express)
                           |
                           v
                  React Incident Dashboard
```

## Services and Ports

- Incident API (Express): `http://localhost:8000`
- Incident Dashboard (React): `http://localhost:3000`
- n8n: `http://localhost:5678` (login: `admin` / `admin`)
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (login: `admin` / `admin`)
- Loki: `http://localhost:3100`
- Simulator metrics: `http://localhost:9000/metrics`

## One-Command Run (Docker)

```cmd
cd /d "c:\AI-powered workflow Automation"
copy .env.example .env
docker compose up --build
```

## API Endpoints (Incident API)

- `GET /health` -> `{ "status": "ok" }`
- `POST /incident-report` (called by n8n)
- `GET /incidents` (dashboard uses this)
- `GET /incidents/:id`

## Demo Workflow (n8n)

An importable n8n workflow is provided:

- `n8n-workflows/demo_incident_detection.json`
- `n8n-workflows/auto_detect_incident.json` (polls every minute and creates incidents automatically)

In n8n:

1. Workflows -> Import from File
2. Import `n8n-workflows/demo_incident_detection.json`
3. (Optional) Import `n8n-workflows/auto_detect_incident.json`
4. Activate the workflow(s)

### Trigger the Demo (Webhook)

The workflow exposes:

- `POST http://localhost:5678/webhook/incident-trigger`

Example:

```cmd
curl -X POST http://localhost:5678/webhook/incident-trigger -H "Content-Type: application/json" -d "{\"service_name\":\"payment-service\",\"reason\":\"demo\"}"
```

This will:

1. Query Prometheus for error rate, latency, DB utilization
2. Query Loki for recent error logs
3. Compute severity (P1/P2/P3) and infer root cause + actions
4. `POST` the incident report to the Incident API

## Demo Script (Preferred)

Run:

```cmd
python scripts\demo_request.py
```

This triggers n8n and prints the latest stored incident.

## Auto-Detection Demo (No Manual Trigger)

To demonstrate "n8n detects it" automatically:

1. In n8n, import and activate `n8n-workflows/auto_detect_incident.json`.
2. Keep the stack running for 2-3 minutes.
3. The `simulator` produces periodic spikes (see `SPIKE_EVERY_SECONDS` / `SPIKE_DURATION_SECONDS` in `docker-compose.yml`).
4. During a spike, the auto workflow will compute severity and, if `severity != P3`, it will `POST /incident-report` to the Incident API.
5. Open the dashboard and refresh:
   - `http://localhost:3000`

If you want to force a spike immediately, temporarily set these in `docker-compose.yml` under the `simulator` service:

- `SPIKE_EVERY_SECONDS=30`
- `SPIKE_DURATION_SECONDS=20`

Then restart:

```cmd
docker compose up --build
```

## Notes

- This repo also contains the earlier FastAPI-based workflow automation prototype under `backend/`, but the incident detection stack uses the Node.js API + React dashboard as specified.
