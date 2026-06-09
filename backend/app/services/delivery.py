"""
Result Delivery Service.

Sends execution results via the configured channels (email, Slack, dashboard).
Each channel is attempted independently so one failure does not block others.
Rich HTML email templates are used for readability.
"""
import json
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from ..config import settings
from ..logging_config import get_logger

logger = get_logger(__name__)


# ── HTML Email Template ────────────────────────────────────────────────────────

def _build_html_email(user_id: str, execution_output: dict) -> str:
    status = execution_output.get("status", "unknown")
    workflow = execution_output.get("workflow_name", "automation")
    correlation_id = execution_output.get("correlation_id", "-")
    run_id = execution_output.get("run_id", "-")
    channels = ", ".join(execution_output.get("channels", []))
    status_color = "#16a34a" if status == "success" else "#dc2626"

    n8n_resp = execution_output.get("n8n_response", {})
    details_rows = ""
    for key, value in n8n_resp.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        details_rows += f"<tr><td style='padding:6px 10px;color:#64748b;white-space:nowrap'>{key}</td><td style='padding:6px 10px'>{value}</td></tr>"

    if not details_rows:
        details_rows = "<tr><td colspan='2' style='padding:6px 10px;color:#94a3b8'>No additional details</td></tr>"

    raw_json = textwrap.indent(json.dumps(execution_output, indent=2), "  ")

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f1f5f9;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);">

        <!-- Header -->
        <tr><td style="background:#0f766e;padding:24px 32px;">
          <h1 style="margin:0;color:#fff;font-size:20px;">AI Workflow Automation</h1>
          <p style="margin:4px 0 0;color:#ccfbf1;font-size:13px;">Execution Result Notification</p>
        </td></tr>

        <!-- Status banner -->
        <tr><td style="padding:24px 32px 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="background:#f8fafc;border-left:4px solid {status_color};border-radius:6px;padding:14px 18px;">
                <span style="font-size:13px;color:#64748b;text-transform:uppercase;letter-spacing:.05em">Status</span><br/>
                <span style="font-size:22px;font-weight:700;color:{status_color}">{status.upper()}</span>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Meta table -->
        <tr><td style="padding:20px 32px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;">
            <tr>
              <td style="padding:6px 0;color:#64748b;width:140px">Workflow</td>
              <td style="padding:6px 0;font-weight:600">{workflow}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#64748b">Run ID</td>
              <td style="padding:6px 0">{run_id}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#64748b">Correlation ID</td>
              <td style="padding:6px 0;font-family:monospace;font-size:12px">{correlation_id}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#64748b">Channels</td>
              <td style="padding:6px 0">{channels or "dashboard"}</td>
            </tr>
          </table>
        </td></tr>

        <!-- n8n details -->
        <tr><td style="padding:20px 32px 0;">
          <p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#0f172a;text-transform:uppercase;letter-spacing:.04em">Execution Details</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
            {details_rows}
          </table>
        </td></tr>

        <!-- Raw JSON collapsible (plain text fallback) -->
        <tr><td style="padding:20px 32px;">
          <details>
            <summary style="cursor:pointer;font-size:13px;color:#0f766e;font-weight:600">Full JSON Output</summary>
            <pre style="background:#f8fafc;padding:12px;border-radius:8px;font-size:12px;overflow-x:auto;margin-top:8px">{raw_json}</pre>
          </details>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:16px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;">
          <p style="margin:0;font-size:12px;color:#94a3b8">
            This message was sent to <strong>{user_id}</strong> by AI Workflow Automation.
            Do not reply to this email.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_plain_email(user_id: str, execution_output: dict) -> str:
    return (
        f"AI Workflow Automation — Execution Result\n"
        f"{'='*50}\n\n"
        f"Status : {execution_output.get('status', 'unknown')}\n"
        f"Workflow: {execution_output.get('workflow_name', '-')}\n"
        f"Run ID  : {execution_output.get('run_id', '-')}\n"
        f"Corr ID : {execution_output.get('correlation_id', '-')}\n\n"
        f"Full output:\n{json.dumps(execution_output, indent=2)}\n"
    )


# ── Service class ──────────────────────────────────────────────────────────────

class ResultDeliveryService:
    @staticmethod
    def deliver(user_id: str, channels: list[str], execution_output: dict) -> dict:
        """
        Attempt delivery on each requested channel independently.

        Returns a dict mapping channel name → status string.
        Possible statuses: "sent", "stored", "failed", "not_configured", "unsupported_channel".
        """
        statuses: dict[str, str] = {}
        for channel in channels:
            channel_key = channel.lower().strip()
            if channel_key == "email":
                statuses["email"] = ResultDeliveryService._send_email(user_id, execution_output)
            elif channel_key == "slack":
                statuses["slack"] = ResultDeliveryService._send_slack(execution_output)
            elif channel_key == "dashboard":
                statuses["dashboard"] = "stored"
            else:
                logger.warning("Unknown delivery channel: %s", channel_key)
                statuses[channel_key] = "unsupported_channel"
        return statuses

    # ── Email ────────────────────────────────────────────────────────────────

    @staticmethod
    def _send_email(user_id: str, execution_output: dict) -> str:
        if not settings.smtp_host:
            logger.warning("SMTP_HOST not configured — skipping email delivery")
            return "not_configured"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"Workflow '{execution_output.get('workflow_name', 'automation')}' "
                f"— {execution_output.get('status', 'result').upper()}"
            )
            msg["From"] = settings.email_from
            msg["To"] = user_id

            plain = MIMEText(_build_plain_email(user_id, execution_output), "plain", "utf-8")
            html = MIMEText(_build_html_email(user_id, execution_output), "html", "utf-8")
            msg.attach(plain)
            msg.attach(html)  # HTML wins in clients that support it

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info("Email sent | to=%s | workflow=%s", user_id, execution_output.get("workflow_name"))
            return "sent"

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed — check SMTP_USER / SMTP_PASSWORD")
            return "failed"
        except smtplib.SMTPConnectError as exc:
            logger.error("SMTP connection error | host=%s | error=%s", settings.smtp_host, exc)
            return "failed"
        except smtplib.SMTPException as exc:
            logger.error("SMTP error sending to %s | error=%s", user_id, exc)
            return "failed"
        except Exception as exc:
            logger.error("Unexpected email delivery error | to=%s | error=%s", user_id, exc, exc_info=True)
            return "failed"

    # ── Slack ────────────────────────────────────────────────────────────────

    @staticmethod
    def _send_slack(execution_output: dict) -> str:
        if not settings.slack_webhook_url:
            logger.debug("SLACK_WEBHOOK_URL not configured — skipping Slack delivery")
            return "not_configured"

        status = execution_output.get("status", "unknown")
        workflow = execution_output.get("workflow_name", "automation")
        correlation_id = execution_output.get("correlation_id", "-")
        color = "#16a34a" if status == "success" else "#dc2626"

        slack_payload = {
            "attachments": [
                {
                    "color": color,
                    "fallback": f"Workflow '{workflow}' — {status.upper()}",
                    "title": f"AI Workflow Automation — {status.upper()}",
                    "fields": [
                        {"title": "Workflow", "value": workflow, "short": True},
                        {"title": "Status", "value": status.upper(), "short": True},
                        {"title": "Run ID", "value": str(execution_output.get("run_id", "-")), "short": True},
                        {"title": "Correlation ID", "value": correlation_id, "short": True},
                    ],
                    "footer": "AI Workflow Automation",
                    "ts": __import__("time").time(),
                }
            ]
        }

        # Append n8n details if available
        n8n = execution_output.get("n8n_response", {})
        if n8n:
            details_text = "\n".join(f"*{k}*: {v}" for k, v in n8n.items() if not isinstance(v, (dict, list)))
            if details_text:
                slack_payload["attachments"][0]["text"] = details_text

        try:
            response = requests.post(
                settings.slack_webhook_url,
                json=slack_payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Slack notification sent | workflow=%s", workflow)
            return "sent"
        except requests.exceptions.HTTPError as exc:
            logger.error("Slack HTTP error | status=%s | body=%s", exc.response.status_code, exc.response.text[:200])
            return "failed"
        except requests.exceptions.ConnectionError as exc:
            logger.error("Slack connection error | error=%s", exc)
            return "failed"
        except Exception as exc:
            logger.error("Unexpected Slack delivery error | error=%s", exc, exc_info=True)
            return "failed"
