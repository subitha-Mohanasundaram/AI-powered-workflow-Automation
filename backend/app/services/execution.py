import time

import requests

from ..config import settings
from ..schemas import WorkflowExecutionResult


class ExecutionEngineService:
    @staticmethod
    def execute(workflow_payload: dict) -> WorkflowExecutionResult:
        webhook_url = f"{settings.n8n_base_url.rstrip('/')}{settings.n8n_execution_webhook_path}"
        attempts = max(1, settings.n8n_retry_attempts)
        backoff = max(0.0, settings.n8n_retry_backoff_seconds)
        last_error = ""

        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(webhook_url, json=workflow_payload, timeout=settings.n8n_timeout_seconds)
                response.raise_for_status()
                data = response.json() if response.content else {"message": "n8n execution accepted"}
                structured = {
                    "run_id": workflow_payload.get("run_id"),
                    "correlation_id": workflow_payload.get("correlation_id"),
                    "workflow_name": workflow_payload.get("workflow_name"),
                    "status": "success",
                    "channels": workflow_payload.get("channels", []),
                    "attempt": attempt,
                    "n8n_response": data,
                }
                return WorkflowExecutionResult(status="success", output=structured)
            except Exception as exc:
                last_error = str(exc)
                if attempt < attempts:
                    time.sleep(backoff * (2 ** (attempt - 1)))

        return WorkflowExecutionResult(
            status="failed",
            output={
                "run_id": workflow_payload.get("run_id"),
                "correlation_id": workflow_payload.get("correlation_id"),
                "workflow_name": workflow_payload.get("workflow_name"),
                "status": "failed",
                "attempts": attempts,
                "error": last_error,
                "fallback_message": "n8n webhook call failed. Configure workflow endpoint and retry.",
            },
        )
