import json
import smtplib
from email.mime.text import MIMEText

import requests

from ..config import settings


class ResultDeliveryService:
    @staticmethod
    def deliver(user_id: str, channels: list[str], execution_output: dict) -> dict:
        statuses = {}
        for channel in channels:
            channel_key = channel.lower().strip()
            if channel_key == "email":
                statuses["email"] = ResultDeliveryService._send_email(user_id, execution_output)
            elif channel_key == "slack":
                statuses["slack"] = ResultDeliveryService._send_slack(execution_output)
            elif channel_key == "dashboard":
                statuses["dashboard"] = "stored"
            else:
                statuses[channel_key] = "unsupported_channel"
        return statuses

    @staticmethod
    def _send_email(user_id: str, execution_output: dict) -> str:
        body = json.dumps(execution_output, indent=2)
        message = MIMEText(body, "plain")
        message["Subject"] = "Workflow Execution Result"
        message["From"] = settings.email_from
        message["To"] = user_id

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
            return "sent"
        except Exception:
            return "failed"

    @staticmethod
    def _send_slack(execution_output: dict) -> str:
        if not settings.slack_webhook_url:
            return "not_configured"
        try:
            response = requests.post(
                settings.slack_webhook_url,
                json={"text": f"Workflow Result:\n```{json.dumps(execution_output, indent=2)}```"},
                timeout=10,
            )
            response.raise_for_status()
            return "sent"
        except Exception:
            return "failed"

