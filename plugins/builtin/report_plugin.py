"""
Report Generation Plugin — wraps the report building logic.
"""
from datetime import UTC, datetime

from plugins.base_plugin import BasePlugin


class ReportPlugin(BasePlugin):
    """Generates structured reports from fetched data."""

    plugin_id = "report_generation"
    display_name = "Report Generator"
    supported_actions = ["report_generation"]

    def execute(self, action: str, params: dict, context: dict) -> dict:
        if action != "report_generation":
            return {"status": "failed", "result": None, "error": f"Unsupported action: {action}"}

        try:
            fetched_data = context.get("fetched_data") or {}
            workflow_name = context.get("workflow_name", "automation")
            raw_request = context.get("raw_request", "")

            report = {
                "title": f"Automated Report — {workflow_name.replace('_', ' ').title()}",
                "generated_at": datetime.now(UTC).isoformat(),
                "source": fetched_data.get("source", "internal"),
                "summary": fetched_data.get("summary", "Data processed successfully."),
                "request": raw_request,
                "record_count": fetched_data.get("records", 0),
            }
            return {"status": "success", "result": report}
        except Exception as exc:
            return {"status": "failed", "result": None, "error": str(exc)}
