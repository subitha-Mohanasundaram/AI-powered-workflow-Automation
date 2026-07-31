

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
