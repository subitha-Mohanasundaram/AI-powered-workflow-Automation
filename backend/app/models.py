"""
SQLAlchemy ORM models.

Uses timezone-aware UTC timestamps (datetime.now(UTC)) instead of the
deprecated datetime.utcnow() which is removed in Python 3.12+.
"""
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    interpreted_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_payload: Mapped[str] = mapped_column(Text, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    execution_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    # Link to scheduled workflow if triggered by scheduler
    scheduled_workflow_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ── Scheduled Workflows ────────────────────────────────────────────────────────

class ScheduledWorkflow(Base):
    """
    A saved workflow with a schedule.
    The user describes the workflow once — it runs automatically on schedule.
    """
    __tablename__ = "scheduled_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The plain English request — what the user wants
    request_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Schedule — cron expression or interval
    schedule_type: Mapped[str] = mapped_column(String(32), nullable=False, default="interval")
    # interval: "every_day", "every_hour", "every_monday", "every_30_minutes"
    # cron: raw cron expression like "0 9 * * 1"
    schedule_value: Mapped[str] = mapped_column(String(64), nullable=False, default="every_day")

    # Delivery configuration
    delivery_channels: Mapped[str] = mapped_column(String(128), nullable=False, default="dashboard")
    delivery_email: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    # Encrypted user context (API keys, custom config, confidential details)
    # Stored as encrypted JSON
    user_context_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # State
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


# ── User Profile (confidential settings per user) ──────────────────────────────

class UserProfile(Base):
    """
    Stores per-user confidential configuration.
    All sensitive values are encrypted at rest.
    """
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    company: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # Encrypted fields — never stored in plaintext
    email_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    smtp_host_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_user_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    smtp_pass_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    slack_webhook_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_api_url_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_api_headers_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extra_context_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


# ── LeetCode Tracker models ────────────────────────────────────────────────────

class LeetCodeStudent(Base):
    __tablename__ = "leetcode_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    real_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    batch: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class LeetCodeReport(Base):
    __tablename__ = "leetcode_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
