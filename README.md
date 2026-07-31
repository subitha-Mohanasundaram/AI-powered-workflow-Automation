# AI-Powered Workflow Automation Platform

A full-stack, production-style automation platform that combines a **FastAPI backend**, **n8n workflow orchestration**, **AI-powered natural language interpretation**, and an **incident detection system** with real-time monitoring.

---
<div align="center">

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
