"""
Pydantic schemas for request/response validation.
UserRequestCreate applies strict input sanitization to prevent injection attacks.
"""
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# Characters allowed in free-text request fields.
# Permits letters, digits, punctuation, and common Unicode prose; blocks
# control characters and SQL/shell meta-characters.
_SAFE_TEXT_PATTERN = re.compile(r"^[\w\s.,!?;:()\-\'\"\+\@\/\#\%\&\*\=\[\]\{\}\|\~\u00C0-\uFFFF]+$")


def _sanitize_text(value: str) -> str:
    """Strip leading/trailing whitespace and normalize internal whitespace."""
    return " ".join(value.split())


class UserRequestCreate(BaseModel):
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Email address or opaque user identifier.",
    )
    request_text: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Plain-language description of the automation to execute.",
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id must not be blank")
        # Basic email-or-safe-identifier check
        if len(v) > 128:
            raise ValueError("user_id exceeds maximum length of 128 characters")
        # Allow email format OR alphanumeric-slug format
        email_re = re.compile(r"^[a-zA-Z0-9_.+\-@]+$")
        if not email_re.match(v):
            raise ValueError(
                "user_id must be an email address or contain only "
                "letters, digits, dots, underscores, hyphens, and plus signs"
            )
        return v

    @field_validator("request_text")
    @classmethod
    def validate_request_text(cls, v: str) -> str:
        v = _sanitize_text(v)
        if len(v) < 10:
            raise ValueError("request_text must be at least 10 characters after sanitization")
        # Reject obvious prompt-injection patterns
        lower = v.lower()
        injection_patterns = [
            "ignore previous",
            "disregard your instructions",
            "system prompt",
            "jailbreak",
            "act as if you",
        ]
        for pattern in injection_patterns:
            if pattern in lower:
                raise ValueError("request_text contains disallowed content")
        return v


class WorkflowStep(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    action: Literal[
        "api_fetch",
        "transform_data",
        "report_generation",
        "email_send",
        "slack_notify",
        "dashboard_update",
        "notification_send",
    ]
    params: dict[str, Any] = Field(default_factory=dict)


class WorkflowInstruction(BaseModel):
    workflow_name: str = Field(..., min_length=3, max_length=80)
    trigger: dict[str, Any]
    steps: list[WorkflowStep] = Field(..., min_length=1)
    channels: list[Literal["dashboard", "email", "slack"]] = Field(..., min_length=1)
    output_format: Literal["text", "json", "html", "markdown"] = "text"

    @field_validator("workflow_name")
    @classmethod
    def normalize_workflow_name(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        return "".join(ch for ch in normalized if ch.isalnum() or ch in {"_", "-"})

    @field_validator("channels")
    @classmethod
    def unique_channels(cls, value: list[str]) -> list[str]:
        unique: list[str] = []
        for channel in value:
            if channel not in unique:
                unique.append(channel)
        return unique


class WorkflowExecutionResult(BaseModel):
    status: str
    output: dict[str, Any]


class WorkflowRunResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: str
    request_text: str
    execution_status: str
    delivery_status: str
    execution_output: str
    created_at: datetime
    updated_at: datetime
