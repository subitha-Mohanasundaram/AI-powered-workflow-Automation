from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class UserRequestCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    request_text: str = Field(..., min_length=5)


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
        unique = []
        for channel in value:
            if channel not in unique:
                unique.append(channel)
        return unique


class WorkflowExecutionResult(BaseModel):
    status: str
    output: dict[str, Any]


class WorkflowRunResponse(BaseModel):
    id: int
    user_id: str
    request_text: str
    execution_status: str
    delivery_status: str
    execution_output: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
