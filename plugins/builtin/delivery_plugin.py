"""
Delivery Plugin — wraps email/Slack delivery services.
"""
from plugins.base_plugin import BasePlugin


class DeliveryPlugin(BasePlugin):
    """Delivers results via email or Slack."""

    plugin_id = "delivery"
    display_name = "Result Delivery"
    supported_actions = ["email_send", "slack_notify", "dashboard_update"]

    def execute(self, action: str, params: dict, context: dict) -> dict:
        if action not in self.supported_actions:
            return {"status": "failed", "result": None, "error": f"Unsupported action: {action}"}

        try:
            execution_output = context.get("execution_output", {})
            user_id = context.get("user_id", "")

            if action == "email_send":
                from backend.app.services.delivery import ResultDeliveryService
                status = ResultDeliveryService._send_email(user_id, execution_output)
                return {"status": "success" if status == "sent" else "failed", "result": {"channel": "email", "delivery_status": status}}

            elif action == "slack_notify":
                from backend.app.services.delivery import ResultDeliveryService
                status = ResultDeliveryService._send_slack(execution_output)
                return {"status": "success" if status == "sent" else "failed", "result": {"channel": "slack", "delivery_status": status}}

            elif action == "dashboard_update":
                return {"status": "success", "result": {"channel": "dashboard", "delivery_status": "stored"}}

        except Exception as exc:
            return {"status": "failed", "result": None, "error": str(exc)}
