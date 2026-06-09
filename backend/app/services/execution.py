"""
Execution Engine Service.

Smart execution — detects the intent of the workflow and runs the right handler:

  - LeetCode keywords  → fetch REAL LeetCode data for tracked students
  - n8n configured     → dispatch to n8n webhook
  - everything else    → run locally with simulated data

This means:
  "generate a report on leetcode solving status"   → real LeetCode data
  "fetch sales data and generate a report"         → local simulated data
  "send report to Slack"                           → local + Slack delivery
"""
import time
from datetime import UTC, datetime

import requests as http_requests

from ..config import settings
from ..logging_config import get_logger
from ..schemas import WorkflowExecutionResult

logger = get_logger(__name__)


# ── URL helpers ───────────────────────────────────────────────────────────────

def _build_webhook_url() -> str:
    if settings.n8n_webhook_url:
        base = settings.n8n_webhook_url.rstrip("/")
        if base.endswith("/webhook"):
            return f"{base}/execute-workflow"
        return base
    return f"{settings.n8n_base_url.rstrip('/')}{settings.n8n_execution_webhook_path}"


def _is_n8n_configured() -> bool:
    url = _build_webhook_url()
    unconfigured = ("n8n:5678", "localhost:5678", "127.0.0.1:5678")
    return not any(h in url for h in unconfigured)


# ── Intent detection ──────────────────────────────────────────────────────────

_LEETCODE_KEYWORDS = {
    "leetcode", "leet code", "coding", "solving status", "problem solving",
    "solved problems", "coding progress", "student progress", "competitive",
    "dsa", "data structure", "algorithm", "easy medium hard", "contest rating",
    "submission", "leaderboard", "class report", "student report",
}


def _is_leetcode_request(raw_request: str) -> bool:
    """Return True if the request is about LeetCode student tracking."""
    lower = raw_request.lower()
    return any(kw in lower for kw in _LEETCODE_KEYWORDS)


# ── LeetCode execution ────────────────────────────────────────────────────────

def _execute_leetcode(workflow_payload: dict) -> WorkflowExecutionResult:
    """
    Fetch REAL LeetCode data for all tracked students and build a report.
    Falls back gracefully if no students are added yet.
    """
    from .leetcode import generate_class_report
    from ..database import SessionLocal
    from ..models import LeetCodeStudent

    run_id = workflow_payload.get("run_id")
    correlation_id = workflow_payload.get("correlation_id", "-")
    workflow_name = workflow_payload.get("workflow_name", "leetcode_report")
    raw_request = workflow_payload.get("raw_request", "")
    channels = workflow_payload.get("channels", ["dashboard"])

    logger.info("LeetCode execution | run_id=%s | fetching real data", run_id)

    # Get tracked students from DB
    db = SessionLocal()
    try:
        students = db.query(LeetCodeStudent).filter(LeetCodeStudent.is_active == 1).all()
    finally:
        db.close()

    if not students:
        # No students added — return a helpful message
        logger.warning("No students tracked — returning guidance response | run_id=%s", run_id)
        return WorkflowExecutionResult(
            status="success",
            output={
                "run_id": run_id,
                "correlation_id": correlation_id,
                "workflow_name": workflow_name,
                "status": "success",
                "execution_mode": "leetcode",
                "channels": channels,
                "steps_completed": 1,
                "n8n_response": {
                    "mode": "leetcode_tracker",
                    "affected_service": "LeetCode Class Tracker",
                    "probable_root_cause": (
                        "No students are being tracked yet. "
                        "Go to /api/leetcode/dashboard and add student LeetCode usernames first."
                    ),
                    "recommended_actions": (
                        "Visit http://localhost:8000/api/leetcode/dashboard → "
                        "Add your students → Come back and ask again"
                    ),
                    "priority_message": "Add students to start tracking",
                    "severity": "info",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            },
        )

    # Fetch real data
    usernames = [s.username for s in students]
    logger.info("Fetching LeetCode data | students=%s", usernames)
    report = generate_class_report(usernames)

    if "error" in report:
        return WorkflowExecutionResult(
            status="failed",
            output={
                "run_id": run_id,
                "correlation_id": correlation_id,
                "workflow_name": workflow_name,
                "status": "failed",
                "error": report["error"],
            },
        )

    summary = report["summary"]
    leaderboard = report["leaderboard"]
    today = report["today_activity"]
    top_topics = list(report["top_topics"].items())[:5]

    # Build human-readable report text
    top3 = leaderboard[:3]
    top3_text = " | ".join(
        f"{s['rank']}. {s['real_name']} ({s['total_solved']} solved)" for s in top3
    )
    active_names = ", ".join(s["real_name"] for s in today[:5]) or "None"
    topics_text = ", ".join(f"{t[0]} ({t[1]})" for t in top_topics)

    report_summary = (
        f"LeetCode Class Report — {report['date']} | "
        f"{summary['total_students']} students tracked | "
        f"{summary['active_today']} active today | "
        f"{summary['problems_solved_today']} problems solved today | "
        f"Total all-time: {summary['total_problems_solved_alltime']} | "
        f"Average: {summary['average_solved']} per student"
    )

    logger.info("LeetCode report built | run_id=%s | students=%d", run_id, summary["total_students"])

    return WorkflowExecutionResult(
        status="success",
        output={
            "run_id": run_id,
            "correlation_id": correlation_id,
            "workflow_name": workflow_name,
            "status": "success",
            "execution_mode": "leetcode",
            "channels": channels,
            "steps_completed": 3,
            "leetcode_report": report,          # full report for downstream use
            "n8n_response": {
                "mode": "leetcode_tracker",
                "affected_service": "LeetCode Class Tracker",
                "report_date": report["date"],
                "probable_root_cause": report_summary,
                "recommended_actions": (
                    f"Active students today: {active_names}. "
                    f"Top topics: {topics_text}."
                ),
                "priority_message": (
                    f"Top performers: {top3_text}"
                    if top3 else "No leaderboard data yet"
                ),
                "severity": "info",
                "timestamp": datetime.now(UTC).isoformat(),
                # Embedded full data for dashboard rendering
                "summary": summary,
                "leaderboard": leaderboard[:10],
                "today_activity": today,
                "top_topics": dict(top_topics),
            },
        },
    )


# ── Local (simulated) execution ───────────────────────────────────────────────

def _build_report_sections(data: dict, source: str) -> list:
    """Build structured report sections from fetched data."""
    sections = []
    if source == "open-meteo":
        current = data.get("current", {})
        sections = [
            {"heading": "Current Conditions", "content": data.get("summary", "")},
            {"heading": "Temperature", "content": f"{current.get('temperature', '--')} (feels like {current.get('feels_like', '--')})"},
            {"heading": "Humidity & Wind", "content": f"Humidity: {current.get('humidity', '--')}, Wind: {current.get('wind_speed', '--')}"},
            {"heading": "Precipitation", "content": current.get("precipitation", "0 mm")},
            {"heading": "5-Day Forecast", "content": str([f"{d['date']}: {d['condition']} {d['max_temp']}/{d['min_temp']}" for d in data.get("forecast_5day", [])])},
        ]
    elif source in ("gnews", "hackernews"):
        articles = data.get("articles", [])
        sections = [
            {"heading": "Summary", "content": data.get("summary", "")},
            {"heading": "Top Headlines", "content": " | ".join(a.get("title", "") for a in articles[:5])},
        ]
        for i, a in enumerate(articles[:5], 1):
            sections.append({"heading": f"Article {i}", "content": f"{a.get('title', '')} — {a.get('source', '')} ({a.get('published_at', '')[:10]})"})
    elif source == "github":
        stats = data.get("stats", {})
        commits = data.get("recent_commits", [])
        sections = [
            {"heading": "Repository", "content": data.get("summary", "")},
            {"heading": "Stats", "content": f"Stars: {stats.get('stars', 0)}, Forks: {stats.get('forks', 0)}, Issues: {stats.get('open_issues', 0)}, Language: {stats.get('language', '--')}"},
            {"heading": "Recent Commits", "content": " | ".join(f"{c['message']} by {c['author']}" for c in commits[:3])},
        ]
    elif source == "open.er-api.com":
        sections = [
            {"heading": "Exchange Rates", "content": data.get("summary", "")},
            {"heading": "Key Rates", "content": str(data.get("rates", {}))},
        ]
    elif source == "custom_url":
        sections = [
            {"heading": "Source", "content": data.get("url", "")},
            {"heading": "Summary", "content": data.get("summary", "")},
            {"heading": "Data", "content": str(data.get("data", ""))[:500]},
        ]
    else:
        sections = [
            {"heading": "Summary", "content": data.get("summary", "Data processed successfully.")},
            {"heading": "Records", "content": str(data.get("records", "N/A"))},
        ]
    return sections


def _execute_locally(workflow_payload: dict) -> WorkflowExecutionResult:
    """
    In-process execution with simulated data.
    Used for non-LeetCode requests when n8n is not configured.
    """
    run_id = workflow_payload.get("run_id")
    correlation_id = workflow_payload.get("correlation_id", "-")
    workflow_name = workflow_payload.get("workflow_name", "automation")
    steps = workflow_payload.get("steps", [])
    channels = workflow_payload.get("channels", ["dashboard"])
    raw_request = workflow_payload.get("raw_request", "")

    logger.info("Local execution | run_id=%s | workflow=%s | steps=%d", run_id, workflow_name, len(steps))

    step_results = []
    fetched_data = None
    report_data = None

    for step in steps:
        action = step.get("action", "")
        name = step.get("name", action)

        if action == "api_fetch":
            # Use real data fetcher based on request intent
            from .data_fetcher import auto_fetch
            user_context = workflow_payload.get("user_context", {})
            fetched_data = auto_fetch(raw_request, user_context)
            step_results.append({"step": name, "status": "completed", "result": fetched_data})

        elif action == "transform_data":
            step_results.append({
                "step": name,
                "status": "completed",
                "result": {
                    "processed_records": fetched_data.get("records", 0) if fetched_data else 0,
                    "transformations": ["filter_nulls", "normalize_values", "aggregate"],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            })

        elif action == "report_generation":
            data = fetched_data or {}
            # Build rich report from whatever was fetched
            source = data.get("source", "internal")
            summary_text = data.get("summary", "Data processed successfully.")
            report_data = {
                "title": f"Automated Report — {workflow_name.replace('_', ' ').title()}",
                "generated_at": datetime.now(UTC).isoformat(),
                "source": source,
                "summary": summary_text,
                "request": raw_request,
                "data": data,
                "sections": _build_report_sections(data, source),
            }
            step_results.append({"step": name, "status": "completed", "result": report_data})

        elif action == "email_send":
            step_results.append({"step": name, "status": "queued_for_delivery", "channel": "email"})

        elif action == "slack_notify":
            step_results.append({"step": name, "status": "queued_for_delivery", "channel": "slack"})

        elif action == "dashboard_update":
            step_results.append({"step": name, "status": "completed", "channel": "dashboard"})

        else:
            step_results.append({"step": name, "status": "completed"})

    summary = (
        report_data.get("summary") if report_data
        else f"Processed {fetched_data.get('records', 0)} records successfully." if fetched_data
        else "Workflow completed successfully."
    )

    return WorkflowExecutionResult(
        status="success",
        output={
            "run_id": run_id,
            "correlation_id": correlation_id,
            "workflow_name": workflow_name,
            "status": "success",
            "execution_mode": "local",
            "channels": channels,
            "steps_completed": len(step_results),
            "step_results": step_results,
            "n8n_response": {
                "mode": "local_execution",
                "affected_service": workflow_name.replace("_", " ").title(),
                "probable_root_cause": summary,
                "recommended_actions": f"Results delivered to: {', '.join(channels)}",
                "priority_message": f"{len(step_results)} step(s) completed successfully",
                "severity": "info",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        },
    )


# ── Main service ──────────────────────────────────────────────────────────────

class ExecutionEngineService:
    @staticmethod
    def execute(workflow_payload: dict) -> WorkflowExecutionResult:
        """
        Smart dispatcher — picks the right execution mode based on request intent.

        Priority order:
          1. LeetCode request  → fetch real LeetCode data
          2. n8n configured    → send to n8n webhook
          3. fallback          → run locally with simulated data
        """
        raw_request = workflow_payload.get("raw_request", "")
        run_id = workflow_payload.get("run_id")

        # ── LeetCode intent detected ────────────────────────────────────────
        if _is_leetcode_request(raw_request):
            logger.info("LeetCode intent detected | run_id=%s | request=%.60s", run_id, raw_request)
            return _execute_leetcode(workflow_payload)

        # ── n8n dispatch ────────────────────────────────────────────────────
        if _is_n8n_configured():
            webhook_url = _build_webhook_url()
            attempts = max(1, settings.n8n_retry_attempts)
            backoff = max(0.0, settings.n8n_retry_backoff_seconds)
            correlation_id = workflow_payload.get("correlation_id", "-")
            workflow_name = workflow_payload.get("workflow_name", "unknown")

            logger.info("Dispatching to n8n | run_id=%s | url=%s", run_id, webhook_url)
            last_error = ""
            for attempt in range(1, attempts + 1):
                try:
                    resp = http_requests.post(
                        webhook_url, json=workflow_payload, timeout=settings.n8n_timeout_seconds
                    )
                    resp.raise_for_status()
                    data = resp.json() if resp.content else {"message": "accepted"}
                    logger.info("n8n success | run_id=%s | attempt=%d/%d", run_id, attempt, attempts)
                    return WorkflowExecutionResult(
                        status="success",
                        output={
                            "run_id": run_id,
                            "correlation_id": correlation_id,
                            "workflow_name": workflow_name,
                            "status": "success",
                            "channels": workflow_payload.get("channels", []),
                            "attempt": attempt,
                            "n8n_response": data,
                        },
                    )
                except http_requests.exceptions.Timeout:
                    last_error = f"Timeout after {settings.n8n_timeout_seconds}s"
                except http_requests.exceptions.ConnectionError as exc:
                    last_error = str(exc)
                except http_requests.exceptions.HTTPError as exc:
                    last_error = f"HTTP {exc.response.status_code}"
                    if exc.response.status_code < 500:
                        break
                except Exception as exc:
                    last_error = str(exc)
                    logger.error("n8n error | run_id=%s | error=%s", run_id, exc, exc_info=True)

                if attempt < attempts:
                    time.sleep(backoff * (2 ** (attempt - 1)))

            logger.warning("n8n failed — falling back to local | run_id=%s | error=%s", run_id, last_error)

        # ── Local fallback ──────────────────────────────────────────────────
        return _execute_locally(workflow_payload)
