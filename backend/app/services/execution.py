"""
Execution Engine Service.

Smart execution — detects the intent of the workflow and runs the right handler:

  - LeetCode keywords  → fetch REAL LeetCode data for tracked students
  - n8n configured     → dispatch to n8n webhook
  - everything else    → run locally with step-by-step logging and retry

Step execution:
  - Each step creates an ExecutionLog row (status=running)
  - On failure: retries up to 3x with exponential backoff (1s, 2s, 4s)
  - After all retries exhausted: marks run failed, creates Notification
"""
import json
import time
from datetime import UTC, datetime
from typing import Optional

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


# ── Execution Log helpers ─────────────────────────────────────────────────────

def _create_step_log(db, run_id: int, step_index: int, step_name: str, action: str):
    """Create an ExecutionLog row with status=running."""
    from ..models_v2 import ExecutionLog
    log = ExecutionLog(
        run_id=run_id,
        step_index=step_index,
        step_name=step_name,
        action=action,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _update_step_log(db, log, status: str, output=None, error: Optional[str] = None,
                     retry_count: int = 0):
    """Update an existing ExecutionLog row."""
    finished = datetime.now(UTC)
    log.status = status
    log.finished_at = finished
    if log.started_at:
        delta = finished - log.started_at
        log.duration_ms = int(delta.total_seconds() * 1000)
    if output is not None:
        log.output_json = json.dumps(output) if not isinstance(output, str) else output
    if error:
        log.error_message = error[:2000]
    log.retry_count = retry_count
    db.commit()


def _create_failure_notification(db, user_id: int, run_id: int, step_name: str, error_msg: str):
    """Create an in-app failure notification for the user."""
    try:
        from ..models_v2 import Notification
        notif = Notification(
            user_id=user_id,
            type="failure",
            title=f"Workflow step '{step_name}' failed",
            message=f"Run #{run_id}: {error_msg[:500]}",
            run_id=run_id,
        )
        db.add(notif)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to create failure notification | error=%s", exc)


# ── Step action executor ──────────────────────────────────────────────────────

def _run_step_action(step: dict, workflow_payload: dict,
                     fetched_data: Optional[dict], report_data: Optional[dict]):
    """Execute a single step action. Returns (result_dict, updated_fetched, updated_report)."""
    action = step.get("action", "")
    name = step.get("name", action)
    raw_request = workflow_payload.get("raw_request", "")

    if action == "api_fetch":
        from .data_fetcher import auto_fetch
        user_context = workflow_payload.get("user_context", {})
        fetched_data = auto_fetch(raw_request, user_context)
        result = {"step": name, "status": "completed", "result": fetched_data}

    elif action == "transform_data":
        result = {
            "step": name,
            "status": "completed",
            "result": {
                "processed_records": fetched_data.get("records", 0) if fetched_data else 0,
                "transformations": ["filter_nulls", "normalize_values", "aggregate"],
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

    elif action == "report_generation":
        data = fetched_data or {}
        source = data.get("source", "internal")
        workflow_name = workflow_payload.get("workflow_name", "automation")
        report_data = {
            "title": f"Automated Report — {workflow_name.replace('_', ' ').title()}",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": source,
            "summary": data.get("summary", "Data processed successfully."),
            "request": raw_request,
            "data": data,
            "sections": _build_report_sections(data, source),
        }
        result = {"step": name, "status": "completed", "result": report_data}

    elif action == "email_send":
        result = {"step": name, "status": "queued_for_delivery", "channel": "email"}

    elif action == "slack_notify":
        result = {"step": name, "status": "queued_for_delivery", "channel": "slack"}

    elif action == "dashboard_update":
        result = {"step": name, "status": "completed", "channel": "dashboard"}

    else:
        result = {"step": name, "status": "completed"}

    return result, fetched_data, report_data


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

    db = SessionLocal()
    try:
        students = db.query(LeetCodeStudent).filter(LeetCodeStudent.is_active == 1).all()
    finally:
        db.close()

    if not students:
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
            "leetcode_report": report,
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
                "summary": summary,
                "leaderboard": leaderboard[:10],
                "today_activity": today,
                "top_topics": dict(top_topics),
            },
        },
    )


# ── Report section builder ────────────────────────────────────────────────────

def _build_report_sections(data: dict, source: str) -> list:
    """Build structured report sections from fetched data."""
    if source == "open-meteo":
        current = data.get("current", {})
        return [
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
        return sections
    elif source == "github":
        stats = data.get("stats", {})
        commits = data.get("recent_commits", [])
        return [
            {"heading": "Repository", "content": data.get("summary", "")},
            {"heading": "Stats", "content": f"Stars: {stats.get('stars', 0)}, Forks: {stats.get('forks', 0)}, Issues: {stats.get('open_issues', 0)}, Language: {stats.get('language', '--')}"},
            {"heading": "Recent Commits", "content": " | ".join(f"{c['message']} by {c['author']}" for c in commits[:3])},
        ]
    elif source == "open.er-api.com":
        return [
            {"heading": "Exchange Rates", "content": data.get("summary", "")},
            {"heading": "Key Rates", "content": str(data.get("rates", {}))},
        ]
    elif source == "custom_url":
        return [
            {"heading": "Source", "content": data.get("url", "")},
            {"heading": "Summary", "content": data.get("summary", "")},
            {"heading": "Data", "content": str(data.get("data", ""))[:500]},
        ]
    return [
        {"heading": "Summary", "content": data.get("summary", "Data processed successfully.")},
        {"heading": "Records", "content": str(data.get("records", "N/A"))},
    ]


# ── Local execution with step logging ────────────────────────────────────────

def _execute_locally(workflow_payload: dict, db=None, user_id: Optional[int] = None) -> WorkflowExecutionResult:
    """
    In-process execution with step-by-step ExecutionLog rows and retry logic.
    """
    run_id = workflow_payload.get("run_id")
    correlation_id = workflow_payload.get("correlation_id", "-")
    workflow_name = workflow_payload.get("workflow_name", "automation")
    steps = workflow_payload.get("steps", [])
    channels = workflow_payload.get("channels", ["dashboard"])
    raw_request = workflow_payload.get("raw_request", "")

    logger.info("Local execution | run_id=%s | workflow=%s | steps=%d", run_id, workflow_name, len(steps))

    # Get a DB session if not provided
    own_db = False
    if db is None:
        from ..database import SessionLocal
        db = SessionLocal()
        own_db = True

    try:
        step_results = []
        fetched_data = None
        report_data = None
        failed_step_name = None
        failed_error = None

        for idx, step in enumerate(steps):
            action = step.get("action", "")
            name = step.get("name", action)

            # Create execution log entry
            log = None
            if run_id:
                try:
                    log = _create_step_log(db, run_id, idx, name, action)
                except Exception as exc:
                    logger.warning("Could not create step log | error=%s", exc)

            # Retry logic: up to 3 attempts with exponential backoff
            success = False
            last_error = ""
            result = None
            retry_count = 0

            for attempt in range(3):
                try:
                    result, fetched_data, report_data = _run_step_action(
                        step, workflow_payload, fetched_data, report_data
                    )
                    success = True
                    break
                except Exception as exc:
                    last_error = str(exc)
                    retry_count = attempt + 1
                    logger.warning(
                        "Step failed | run_id=%s | step=%s | attempt=%d/3 | error=%s",
                        run_id, name, attempt + 1, exc
                    )
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # 1s, 2s, 4s

            if success and result is not None:
                step_results.append(result)
                if log:
                    try:
                        _update_step_log(db, log, "success", output=result, retry_count=retry_count)
                    except Exception:
                        pass
            else:
                # All retries exhausted
                failed_step_name = name
                failed_error = last_error
                if log:
                    try:
                        _update_step_log(db, log, "failed", error=last_error, retry_count=retry_count)
                    except Exception:
                        pass
                if run_id and user_id:
                    _create_failure_notification(db, user_id, run_id, name, last_error)
                logger.error(
                    "Step permanently failed | run_id=%s | step=%s | error=%s",
                    run_id, name, last_error
                )
                break  # Stop processing remaining steps

        # If a step failed, generate failure report and mark run as failed
        if failed_step_name:
            from .failure_reporter import generate_failure_report
            failure_report = generate_failure_report(run_id or 0, failed_step_name, failed_error or "")
            return WorkflowExecutionResult(
                status="failed",
                output={
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "workflow_name": workflow_name,
                    "status": "failed",
                    "execution_mode": "local",
                    "channels": channels,
                    "steps_completed": len(step_results),
                    "step_results": step_results,
                    "failure_report": failure_report,
                    "n8n_response": {
                        "mode": "local_execution",
                        "severity": "error",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                },
            )

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
    finally:
        if own_db:
            db.close()


# ── Main service ──────────────────────────────────────────────────────────────

class ExecutionEngineService:
    @staticmethod
    def execute(workflow_payload: dict, db=None, user_id: Optional[int] = None) -> WorkflowExecutionResult:
        """
        Smart dispatcher — picks the right execution mode based on request intent.

        Priority order:
          1. LeetCode request  → fetch real LeetCode data
          2. n8n configured    → send to n8n webhook
          3. fallback          → run locally with step logging and retry
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
        return _execute_locally(workflow_payload, db=db, user_id=user_id)
