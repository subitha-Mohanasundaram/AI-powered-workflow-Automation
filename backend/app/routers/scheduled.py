"""
Scheduled Workflows Router.

Endpoints:
  POST   /api/scheduled              — create a new scheduled workflow
  GET    /api/scheduled              — list all scheduled workflows for a user
  GET    /api/scheduled/{id}         — get one scheduled workflow
  PUT    /api/scheduled/{id}         — update schedule/config
  DELETE /api/scheduled/{id}         — delete (stop) a scheduled workflow
  POST   /api/scheduled/{id}/run     — run immediately (manual trigger)
  POST   /api/scheduled/{id}/pause   — pause the schedule
  POST   /api/scheduled/{id}/resume  — resume the schedule
  GET    /api/scheduled/{id}/history — run history for this workflow

  POST   /api/profile                — save user profile (encrypted)
  GET    /api/profile/{user_id}      — get user profile (masked secrets)
"""
import json
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..logging_config import get_logger
from ..models import ScheduledWorkflow, UserProfile, WorkflowRun
from ..security import require_api_key
from ..services.encryption import decrypt, encrypt, mask
from ..services.scheduler import (
    get_schedule_label,
    parse_schedule_from_text,
    register_workflow_job,
    run_scheduled_workflow,
    unregister_workflow_job,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["scheduled"],
    dependencies=[Depends(require_api_key)],
)


# ── Request / Response models ─────────────────────────────────────────────────

class CreateScheduledWorkflowRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128, description="Your user ID or email")
    name: str = Field(..., min_length=3, max_length=128, description="A name for this workflow")
    description: str = Field(default="", max_length=500)

    request_text: str = Field(
        ..., min_length=10, max_length=2000,
        description="Plain English description of what this workflow should do",
        examples=[
            "Fetch weather report for Chennai and send to my email daily",
            "Generate a LeetCode progress report for my class every Monday",
            "Fetch top tech news and post to Slack every morning",
        ]
    )

    # Schedule
    schedule: str = Field(
        default="every_day",
        description=(
            "When to run: every_day, every_hour, every_monday, every_weekday, "
            "every_30_minutes, every_6_hours, or plain English like 'every Monday at 9am'"
        )
    )

    # Delivery
    delivery_channels: str = Field(
        default="dashboard",
        description="Comma-separated: dashboard, email, slack"
    )
    delivery_email: str = Field(default="", description="Email address for report delivery")

    # User context — confidential, will be encrypted
    user_context: dict = Field(
        default_factory=dict,
        description=(
            "Your confidential workflow configuration. All stored encrypted. "
            "Keys: custom_api_url, custom_api_key, custom_api_headers, "
            "city (for weather), github_repo, news_topic, base_currency, "
            "smtp_host, smtp_user, smtp_pass, slack_webhook"
        )
    )


class UpdateScheduledWorkflowRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=500)
    request_text: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    schedule: Optional[str] = None
    delivery_channels: Optional[str] = None
    delivery_email: Optional[str] = None
    user_context: Optional[dict] = None


class SaveUserProfileRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(default="", max_length=128)
    company: str = Field(default="", max_length=128)
    email: str = Field(default="", description="Your email for report delivery")
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_pass: str = Field(default="", description="Stored encrypted")
    slack_webhook: str = Field(default="", description="Slack incoming webhook URL — stored encrypted")
    custom_api_url: str = Field(default="", description="Your data source URL — stored encrypted")
    custom_api_key: str = Field(default="", description="API key for your data source — stored encrypted")
    custom_api_headers: dict = Field(default_factory=dict, description="Custom HTTP headers — stored encrypted")
    extra_context: dict = Field(default_factory=dict, description="Any extra config — stored encrypted")


# ── Scheduled workflow CRUD ───────────────────────────────────────────────────

@router.post("/scheduled", summary="Create a scheduled workflow")
def create_scheduled(body: CreateScheduledWorkflowRequest, db: Session = Depends(get_db)) -> dict:
    # Parse schedule from text if it looks like plain English
    schedule_value = body.schedule
    if " " in schedule_value and not schedule_value.startswith("cron:") and schedule_value not in (
        "every_day", "every_hour", "every_monday", "every_weekday",
        "every_30_minutes", "every_6_hours", "every_minute", "every_15_minutes",
    ):
        schedule_value = parse_schedule_from_text(body.schedule)

    # Encrypt user context
    ctx_encrypted = ""
    if body.user_context:
        ctx_encrypted = encrypt(json.dumps(body.user_context))

    sw = ScheduledWorkflow(
        user_id=body.user_id,
        name=body.name,
        description=body.description,
        request_text=body.request_text,
        schedule_type="cron" if schedule_value.startswith("cron:") else "interval",
        schedule_value=schedule_value,
        delivery_channels=body.delivery_channels,
        delivery_email=body.delivery_email or body.user_id,
        user_context_encrypted=ctx_encrypted,
        is_active=1,
    )
    db.add(sw)
    db.commit()
    db.refresh(sw)

    # Register with scheduler
    register_workflow_job(sw.id, sw.schedule_value)

    logger.info("Scheduled workflow created | id=%d | user=%s | schedule=%s", sw.id, sw.user_id, schedule_value)
    return _format_workflow(sw)


@router.get("/scheduled", summary="List all scheduled workflows")
def list_scheduled(user_id: str, db: Session = Depends(get_db)) -> dict:
    workflows = (
        db.query(ScheduledWorkflow)
        .filter(ScheduledWorkflow.user_id == user_id)
        .order_by(ScheduledWorkflow.created_at.desc())
        .all()
    )
    return {
        "user_id": user_id,
        "count": len(workflows),
        "workflows": [_format_workflow(sw) for sw in workflows],
    }


@router.get("/scheduled/{workflow_id}", summary="Get a scheduled workflow")
def get_scheduled(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _format_workflow(sw)


@router.put("/scheduled/{workflow_id}", summary="Update a scheduled workflow")
def update_scheduled(
    workflow_id: int, body: UpdateScheduledWorkflowRequest, db: Session = Depends(get_db)
) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.name is not None:
        sw.name = body.name
    if body.description is not None:
        sw.description = body.description
    if body.request_text is not None:
        sw.request_text = body.request_text
    if body.delivery_channels is not None:
        sw.delivery_channels = body.delivery_channels
    if body.delivery_email is not None:
        sw.delivery_email = body.delivery_email
    if body.user_context is not None:
        sw.user_context_encrypted = encrypt(json.dumps(body.user_context))
    if body.schedule is not None:
        schedule_value = body.schedule
        if " " in schedule_value and not schedule_value.startswith("cron:"):
            schedule_value = parse_schedule_from_text(body.schedule)
        sw.schedule_value = schedule_value
        register_workflow_job(sw.id, sw.schedule_value)

    db.commit()
    db.refresh(sw)
    logger.info("Scheduled workflow updated | id=%d", workflow_id)
    return _format_workflow(sw)


@router.delete("/scheduled/{workflow_id}", summary="Delete a scheduled workflow")
def delete_scheduled(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")
    unregister_workflow_job(workflow_id)
    sw.is_active = 0
    db.commit()
    return {"message": f"Workflow '{sw.name}' deleted", "id": workflow_id}


@router.post("/scheduled/{workflow_id}/run", summary="Run a scheduled workflow immediately")
def run_now(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")
    logger.info("Manual trigger | id=%d | name=%s", workflow_id, sw.name)
    run_scheduled_workflow(workflow_id)
    db.refresh(sw)
    return {
        "message": f"Workflow '{sw.name}' executed",
        "last_status": sw.last_status,
        "total_runs": sw.total_runs,
    }


@router.post("/scheduled/{workflow_id}/pause", summary="Pause a scheduled workflow")
def pause_scheduled(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")
    unregister_workflow_job(workflow_id)
    sw.is_active = 0
    db.commit()
    return {"message": f"Workflow '{sw.name}' paused", "id": workflow_id}


@router.post("/scheduled/{workflow_id}/resume", summary="Resume a paused workflow")
def resume_scheduled(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")
    register_workflow_job(sw.id, sw.schedule_value)
    sw.is_active = 1
    db.commit()
    return {"message": f"Workflow '{sw.name}' resumed", "id": workflow_id}


@router.get("/scheduled/{workflow_id}/history", summary="Run history for a scheduled workflow")
def workflow_history(workflow_id: int, limit: int = 20, db: Session = Depends(get_db)) -> dict:
    sw = db.query(ScheduledWorkflow).filter(ScheduledWorkflow.id == workflow_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.scheduled_workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "workflow_id": workflow_id,
        "name": sw.name,
        "total_runs": sw.total_runs,
        "runs": [
            {
                "id": r.id,
                "execution_status": r.execution_status,
                "delivery_status": r.delivery_status,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ],
    }


# ── User profile ──────────────────────────────────────────────────────────────

@router.post("/profile", summary="Save user profile with confidential settings")
def save_profile(body: SaveUserProfileRequest, db: Session = Depends(get_db)) -> dict:
    profile = db.query(UserProfile).filter(UserProfile.user_id == body.user_id).first()
    if not profile:
        profile = UserProfile(user_id=body.user_id)
        db.add(profile)

    profile.display_name = body.display_name
    profile.company = body.company
    profile.smtp_port = body.smtp_port

    # Encrypt all sensitive fields
    profile.email_encrypted = encrypt(body.email) if body.email else ""
    profile.smtp_host_encrypted = encrypt(body.smtp_host) if body.smtp_host else ""
    profile.smtp_user_encrypted = encrypt(body.smtp_user) if body.smtp_user else ""
    profile.smtp_pass_encrypted = encrypt(body.smtp_pass) if body.smtp_pass else ""
    profile.slack_webhook_encrypted = encrypt(body.slack_webhook) if body.slack_webhook else ""
    profile.custom_api_url_encrypted = encrypt(body.custom_api_url) if body.custom_api_url else ""
    profile.custom_api_key_encrypted = encrypt(body.custom_api_key) if body.custom_api_key else ""
    if body.custom_api_headers:
        profile.custom_api_headers_encrypted = encrypt(json.dumps(body.custom_api_headers))
    if body.extra_context:
        profile.extra_context_encrypted = encrypt(json.dumps(body.extra_context))

    db.commit()
    db.refresh(profile)
    logger.info("User profile saved | user_id=%s", body.user_id)
    return {"message": "Profile saved securely", "user_id": body.user_id, "company": body.company}


@router.get("/profile/{user_id}", summary="Get user profile (secrets are masked)")
def get_profile(user_id: str, db: Session = Depends(get_db)) -> dict:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "company": profile.company,
        "smtp_port": profile.smtp_port,
        "email": mask(decrypt(profile.email_encrypted)) if profile.email_encrypted else "",
        "smtp_host": decrypt(profile.smtp_host_encrypted) if profile.smtp_host_encrypted else "",
        "smtp_user": mask(decrypt(profile.smtp_user_encrypted)) if profile.smtp_user_encrypted else "",
        "smtp_pass": "****" if profile.smtp_pass_encrypted else "",
        "slack_webhook": mask(decrypt(profile.slack_webhook_encrypted)) if profile.slack_webhook_encrypted else "",
        "custom_api_url": decrypt(profile.custom_api_url_encrypted) if profile.custom_api_url_encrypted else "",
        "custom_api_key": "****" if profile.custom_api_key_encrypted else "",
        "has_custom_headers": bool(profile.custom_api_headers_encrypted),
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _format_workflow(sw: ScheduledWorkflow) -> dict:
    return {
        "id": sw.id,
        "user_id": sw.user_id,
        "name": sw.name,
        "description": sw.description,
        "request_text": sw.request_text,
        "schedule": sw.schedule_value,
        "schedule_label": get_schedule_label(sw.schedule_value),
        "delivery_channels": sw.delivery_channels,
        "delivery_email": sw.delivery_email,
        "is_active": bool(sw.is_active),
        "last_run_at": sw.last_run_at.isoformat() if sw.last_run_at else None,
        "next_run_at": sw.next_run_at.isoformat() if sw.next_run_at else None,
        "total_runs": sw.total_runs,
        "last_status": sw.last_status,
        "has_confidential_config": bool(sw.user_context_encrypted),
        "created_at": sw.created_at.isoformat(),
    }
