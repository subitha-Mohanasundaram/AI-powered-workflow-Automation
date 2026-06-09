"""
Workflow Scheduler Service.

Manages scheduled workflows using APScheduler.
Workflows run automatically on their defined schedule and results
are saved to the database exactly like manual runs.

Schedule types supported:
  every_minute      - every 1 minute (testing)
  every_15_minutes  - every 15 minutes
  every_30_minutes  - every 30 minutes
  every_hour        - every 1 hour
  every_6_hours     - every 6 hours
  every_day         - every day at 08:00 local time
  every_monday      - every Monday at 08:00
  every_weekday     - Mon-Fri at 08:00
  cron:<expr>       - raw cron: "0 9 * * 1" = every Monday 9am
"""
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..logging_config import get_logger

logger = get_logger(__name__)

# Singleton scheduler
_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
        logger.info("APScheduler initialised")
    return _scheduler


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        logger.info("Scheduler stopped")


# ── Schedule parsing ──────────────────────────────────────────────────────────

_SCHEDULE_MAP = {
    "every_minute":      IntervalTrigger(minutes=1),
    "every_15_minutes":  IntervalTrigger(minutes=15),
    "every_30_minutes":  IntervalTrigger(minutes=30),
    "every_hour":        IntervalTrigger(hours=1),
    "every_6_hours":     IntervalTrigger(hours=6),
    "every_day":         CronTrigger(hour=8, minute=0),
    "every_monday":      CronTrigger(day_of_week="mon", hour=8, minute=0),
    "every_weekday":     CronTrigger(day_of_week="mon-fri", hour=8, minute=0),
}

_SCHEDULE_LABELS = {
    "every_minute": "Every minute",
    "every_15_minutes": "Every 15 minutes",
    "every_30_minutes": "Every 30 minutes",
    "every_hour": "Every hour",
    "every_6_hours": "Every 6 hours",
    "every_day": "Every day at 8:00 AM",
    "every_monday": "Every Monday at 8:00 AM",
    "every_weekday": "Every weekday (Mon–Fri) at 8:00 AM",
}


def parse_schedule_from_text(text: str) -> str:
    """Infer schedule value from plain English text."""
    lower = text.lower()
    if "every minute" in lower or "every 1 minute" in lower:
        return "every_minute"
    if "15 min" in lower:
        return "every_15_minutes"
    if "30 min" in lower or "half hour" in lower:
        return "every_30_minutes"
    if "every hour" in lower or "hourly" in lower:
        return "every_hour"
    if "6 hour" in lower:
        return "every_6_hours"
    if "monday" in lower or "every week" in lower or "weekly" in lower:
        return "every_monday"
    if "weekday" in lower or "working day" in lower:
        return "every_weekday"
    if "daily" in lower or "every day" in lower or "each day" in lower:
        return "every_day"
    return "every_day"  # default


def get_trigger(schedule_value: str):
    """Return an APScheduler trigger from a schedule_value string."""
    if schedule_value in _SCHEDULE_MAP:
        return _SCHEDULE_MAP[schedule_value]
    if schedule_value.startswith("cron:"):
        expr = schedule_value[5:].strip()
        parts = expr.split()
        if len(parts) == 5:
            return CronTrigger(
                minute=parts[0], hour=parts[1],
                day=parts[2], month=parts[3], day_of_week=parts[4],
            )
    logger.warning("Unknown schedule '%s' — defaulting to daily", schedule_value)
    return CronTrigger(hour=8, minute=0)


def get_schedule_label(schedule_value: str) -> str:
    return _SCHEDULE_LABELS.get(schedule_value, schedule_value)


# ── Job execution ─────────────────────────────────────────────────────────────

def run_scheduled_workflow(scheduled_workflow_id: int) -> None:
    """
    Called by APScheduler when a workflow's schedule fires.
    Executes the workflow and saves the result to the database.
    """
    from ..database import SessionLocal
    from ..models import ScheduledWorkflow, WorkflowRun
    from ..services.ai import AIInterpreterService
    from ..services.execution import ExecutionEngineService
    from ..services.workflow_generator import WorkflowGeneratorService
    from ..services.delivery import ResultDeliveryService
    from ..services.encryption import decrypt

    db = SessionLocal()
    try:
        sw = db.query(ScheduledWorkflow).filter(
            ScheduledWorkflow.id == scheduled_workflow_id,
            ScheduledWorkflow.is_active == 1,
        ).first()

        if not sw:
            logger.warning("Scheduled workflow %d not found or inactive", scheduled_workflow_id)
            return

        logger.info(
            "Running scheduled workflow | id=%d | name=%s | user=%s",
            sw.id, sw.name, sw.user_id,
        )

        # Decrypt user context
        user_context = {}
        if sw.user_context_encrypted:
            try:
                user_context = json.loads(decrypt(sw.user_context_encrypted))
            except Exception as exc:
                logger.error("Failed to decrypt user context | id=%d | error=%s", sw.id, exc)

        correlation_id = str(uuid.uuid4())

        # AI interpretation
        instruction = AIInterpreterService.interpret_request(sw.request_text)

        # Override channels from saved config
        saved_channels = [c.strip() for c in sw.delivery_channels.split(",") if c.strip()]
        if saved_channels:
            instruction.channels = saved_channels  # type: ignore

        # Create run record
        run = WorkflowRun(
            user_id=sw.user_id,
            request_text=sw.request_text,
            interpreted_instructions=instruction.model_dump_json(),
            workflow_payload="{}",
            execution_status="pending",
            delivery_status="pending",
            execution_output="{}",
            scheduled_workflow_id=sw.id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Generate and execute
        payload = WorkflowGeneratorService.generate_payload(
            instruction=instruction,
            run_id=run.id,
            raw_request=sw.request_text,
            correlation_id=correlation_id,
        )
        # Inject user context into payload for data fetcher
        payload["user_context"] = user_context
        run.workflow_payload = json.dumps(payload)

        result = ExecutionEngineService.execute(payload)
        run.execution_status = result.status
        run.execution_output = json.dumps(result.output)

        # Deliver
        delivery_email = sw.delivery_email or sw.user_id
        delivery_result = ResultDeliveryService.deliver(
            user_id=delivery_email,
            channels=instruction.channels,
            execution_output=result.output,
        )
        if delivery_result and all(s in {"sent", "stored"} for s in delivery_result.values()):
            run.delivery_status = "success"
        elif any(s == "failed" for s in delivery_result.values()):
            run.delivery_status = "partial_or_failed"
        else:
            run.delivery_status = "pending_or_skipped"

        db.add(run)

        # Update scheduled workflow stats
        sw.last_run_at = datetime.now(UTC)
        sw.total_runs += 1
        sw.last_status = result.status
        db.add(sw)
        db.commit()

        logger.info(
            "Scheduled workflow completed | id=%d | run_id=%d | status=%s",
            sw.id, run.id, result.status,
        )

    except Exception as exc:
        logger.error("Scheduled workflow error | id=%d | error=%s", scheduled_workflow_id, exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


# ── Register / unregister jobs ────────────────────────────────────────────────

def register_workflow_job(scheduled_workflow_id: int, schedule_value: str) -> None:
    """Add or replace a job in the scheduler."""
    sched = get_scheduler()
    job_id = f"workflow_{scheduled_workflow_id}"
    trigger = get_trigger(schedule_value)

    # Remove existing job if any
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    sched.add_job(
        run_scheduled_workflow,
        trigger=trigger,
        id=job_id,
        args=[scheduled_workflow_id],
        replace_existing=True,
        misfire_grace_time=300,  # 5 min grace period
    )
    logger.info("Job registered | id=%s | schedule=%s", job_id, schedule_value)


def unregister_workflow_job(scheduled_workflow_id: int) -> None:
    """Remove a job from the scheduler."""
    sched = get_scheduler()
    job_id = f"workflow_{scheduled_workflow_id}"
    if sched.get_job(job_id):
        sched.remove_job(job_id)
        logger.info("Job removed | id=%s", job_id)


def reload_all_jobs() -> int:
    """
    Load all active scheduled workflows from DB and register them.
    Called on application startup.
    """
    from ..database import SessionLocal
    from ..models import ScheduledWorkflow

    db = SessionLocal()
    count = 0
    try:
        workflows = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.is_active == 1).all()
        for sw in workflows:
            register_workflow_job(sw.id, sw.schedule_value)
            count += 1
        logger.info("Reloaded %d scheduled workflows", count)
    except Exception as exc:
        logger.error("Failed to reload jobs | error=%s", exc)
    finally:
        db.close()
    return count
