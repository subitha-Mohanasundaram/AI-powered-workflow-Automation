"""
API Fetch Plugin — wraps the data_fetcher.auto_fetch service.
"""
import sys
import os

# Allow importing from the backend app when plugins run in isolation
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from plugins.base_plugin import BasePlugin


class ApiFetchPlugin(BasePlugin):
    """Fetches real-time data from public APIs based on the workflow request."""

    plugin_id = "api_fetch"
    display_name = "API Data Fetcher"
    supported_actions = ["api_fetch"]

    def execute(self, action: str, params: dict, context: dict) -> dict:
        if action != "api_fetch":
            return {"status": "failed", "result": None, "error": f"Unsupported action: {action}"}

        try:
            from backend.app.services.data_fetcher import auto_fetch
            raw_request = context.get("raw_request", "")
            user_context = context.get("user_context", {})
            data = auto_fetch(raw_request, user_context)
            return {"status": "success", "result": data}
        except Exception as exc:
            return {"status": "failed", "result": None, "error": str(exc)}
