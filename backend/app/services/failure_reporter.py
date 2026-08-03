"""
Failure Reporter Service — generates AI-powered improvement suggestions
when a workflow execution fails.
"""
import json
from datetime import UTC, datetime
from typing import Optional

from ..config import settings
from ..logging_config import get_logger

logger = get_logger(__name__)

_FAILURE_PROMPT = """You are a workflow automation expert. A workflow step failed.
Analyze the error and provide 1-3 concise, actionable improvement suggestions.

Return ONLY a valid JSON object with this structure:
{
  "suggestions": ["suggestion 1", "suggestion 2", "suggestion 3"]
}

Keep each suggestion under 150 characters. Focus on concrete fixes."""


def generate_failure_report(
    run_id: int,
    failed_step: str,
    error_msg: str,
) -> dict:
    """
    Generate a failure report with AI improvement suggestions.
    Falls back to rule-based suggestions if AI is unavailable.

    Returns dict with: failed_step, error_message, suggestions, timestamp
    """
    suggestions = _get_ai_suggestions(failed_step, error_msg)

    report = {
        "failed_step": failed_step,
        "error_message": error_msg,
        "suggestions": suggestions,
        "timestamp": datetime.now(UTC).isoformat(),
        "run_id": run_id,
    }
    logger.info("Failure report generated | run_id=%d | step=%s | suggestions=%d",
                run_id, failed_step, len(suggestions))
    return report


def _get_ai_suggestions(failed_step: str, error_msg: str) -> list[str]:
    """Call Groq/OpenAI for suggestions; fall back to heuristics on failure."""
    if not settings.ai_api_key or settings.ai_api_key in ("replace_me", ""):
        return _heuristic_suggestions(failed_step, error_msg)

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url.rstrip("/"),
            timeout=15,
            max_retries=1,
        )
        user_message = (
            f"Failed step: {failed_step}\n"
            f"Error message: {error_msg[:500]}"
        )
        response = client.chat.completions.create(
            model=settings.ai_model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": _FAILURE_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw = response.choices[0].message.content or ""
        # Extract JSON
        import re
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            data = json.loads(brace.group(0))
            suggestions = data.get("suggestions", [])
            if isinstance(suggestions, list) and suggestions:
                return [str(s)[:200] for s in suggestions[:3]]
    except Exception as exc:
        logger.warning("AI failure report generation failed | error=%s", exc)

    return _heuristic_suggestions(failed_step, error_msg)


def _heuristic_suggestions(failed_step: str, error_msg: str) -> list[str]:
    """Rule-based fallback suggestions based on common error patterns."""
    suggestions = []
    lower_error = error_msg.lower()
    lower_step = failed_step.lower()

    if "timeout" in lower_error or "timed out" in lower_error:
        suggestions.append("Increase the timeout threshold for this step or optimize the target API.")
        suggestions.append("Consider adding a retry mechanism with exponential backoff.")
    elif "connection" in lower_error or "network" in lower_error:
        suggestions.append("Check network connectivity and ensure the target endpoint is reachable.")
        suggestions.append("Verify firewall rules and DNS resolution for the target host.")
    elif "401" in lower_error or "unauthorized" in lower_error or "authentication" in lower_error:
        suggestions.append("Verify API credentials are correct and not expired.")
        suggestions.append("Ensure the API key or OAuth token has the required permissions.")
    elif "404" in lower_error or "not found" in lower_error:
        suggestions.append("Check the endpoint URL or resource path is correct.")
        suggestions.append("Verify the resource exists and has not been deleted or moved.")
    elif "500" in lower_error or "server error" in lower_error:
        suggestions.append("The target service encountered an internal error — retry after a delay.")
        suggestions.append("Contact the service provider if the error persists.")
    elif "fetch" in lower_step or "api" in lower_step:
        suggestions.append("Verify the API endpoint URL and request parameters are correct.")
        suggestions.append("Check if the API rate limit has been reached.")
    elif "email" in lower_step or "smtp" in lower_step:
        suggestions.append("Verify SMTP credentials and server configuration.")
        suggestions.append("Ensure the recipient email address is valid.")
    elif "slack" in lower_step:
        suggestions.append("Check the Slack webhook URL is valid and the channel still exists.")
    else:
        suggestions.append("Review the step configuration and input parameters.")
        suggestions.append("Check logs for detailed error context.")

    if not suggestions:
        suggestions.append("Review the step inputs and retry the workflow.")

    return suggestions[:3]
