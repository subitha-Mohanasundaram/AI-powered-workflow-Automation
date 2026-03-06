import json

import requests
from pydantic import ValidationError

from ..config import settings
from ..schemas import WorkflowInstruction


class AIInterpreterService:
    @staticmethod
    def interpret_request(request_text: str) -> WorkflowInstruction:
        if not settings.ai_api_key:
            return AIInterpreterService._fallback_instruction(request_text)

        prompt = (
            "Convert user automation request into strict JSON with keys: "
            "workflow_name, trigger, steps, channels, output_format. "
            "Allowed actions: api_fetch, transform_data, report_generation, email_send, "
            "slack_notify, dashboard_update, notification_send. "
            "Allowed channels: dashboard, email, slack. "
            "Return only valid JSON object."
        )

        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.ai_model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": request_text},
            ],
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=settings.ai_timeout_seconds)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return WorkflowInstruction(**parsed)
        except (ValidationError, ValueError, KeyError, requests.RequestException):
            return AIInterpreterService._fallback_instruction(request_text)

    @staticmethod
    def _fallback_instruction(request_text: str) -> WorkflowInstruction:
        channels = AIInterpreterService._infer_channels(request_text)
        steps = [{"name": "fetch_data", "action": "api_fetch"}]
        if "report" in request_text.lower() or "summary" in request_text.lower():
            steps.append({"name": "generate_report", "action": "report_generation"})
        if "email" in channels:
            steps.append({"name": "send_email", "action": "email_send"})
        if "dashboard" in channels:
            steps.append({"name": "update_dashboard", "action": "dashboard_update"})

        return WorkflowInstruction(
            workflow_name="generic_automation",
            trigger={"type": "manual", "source": "api"},
            steps=steps,
            channels=channels,
            output_format="text",
        )

    @staticmethod
    def _infer_channels(request_text: str) -> list[str]:
        text = request_text.lower()
        channels = []
        if "email" in text or "mail" in text:
            channels.append("email")
        if "slack" in text:
            channels.append("slack")
        if "dashboard" in text:
            channels.append("dashboard")
        if not channels:
            channels = ["dashboard"]
        return channels
