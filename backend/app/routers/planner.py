"""
Phase 3 — AI Planner Router

POST /api/v1/planner/plan        — full planning pipeline
POST /api/v1/planner/clarify     — submit answer to a clarification question
GET  /api/v1/planner/session     — get current session conversation history
DELETE /api/v1/planner/session   — clear session memory
GET  /api/v1/planner/schema      — return the WorkflowPlan JSON schema
GET  /api/v1/planner/health      — planner health check
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..security import require_api_key
from ..services.ai_planner import (
    AIPlannerService,
    PlannerRequest,
    PlannerResponse,
    WorkflowPlan,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/planner",
    tags=["AI Planner"],
    dependencies=[Depends(require_api_key)],
)


# ── Request / Response models ─────────────────────────────────────────────────

class PlanRequest(BaseModel):
    request_text: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language automation request",
        examples=[
            "Every morning send weather and AI news to my email",
            "When a GitHub PR is merged, post a Slack notification",
            "Fetch USD to INR exchange rate daily and show on dashboard",
        ],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for multi-turn conversations. Auto-generated if not provided.",
    )
    user_context: dict = Field(
        default_factory=dict,
        description="Known user settings (email, city, timezone, etc.) to improve accuracy.",
    )


class ClarifyRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from the prior /plan call")
    answer: str = Field(..., min_length=1, max_length=1000,
                        description="User's answer to the clarification question")
    original_request: str = Field(..., min_length=3, max_length=2000,
                                   description="The original automation request")


class SessionResponse(BaseModel):
    session_id: str
    history: list[dict]
    turn_count: int


class SchemaResponse(BaseModel):
    json_schema: dict
    description: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/plan",
    response_model=PlannerResponse,
    summary="Plan a workflow from natural language",
    description=(
        "The core AI Planner endpoint. Accepts a natural language automation request "
        "and returns a complete WorkflowPlan with intent analysis, trigger detection, "
        "ordered steps, integration identification, missing info detection, confidence "
        "score, and a plain-English explanation. "
        "If confidence is low, returns `status: needs_clarification` with a follow-up question."
    ),
    responses={
        200: {"description": "Plan generated successfully or clarification needed"},
        422: {"description": "Request validation failed"},
        503: {"description": "AI service temporarily unavailable"},
    },
)
def plan_workflow(body: PlanRequest, request: Request) -> PlannerResponse:
    session_id = body.session_id or str(uuid.uuid4())
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

    logger.info(
        "Planner request | session=%s | text=%.80s | req_id=%s",
        session_id, body.request_text, request_id,
    )

    planner_req = PlannerRequest(
        request_text=body.request_text,
        session_id=session_id,
        user_context=body.user_context,
    )

    response = AIPlannerService.plan(planner_req)
    response.request_id = request_id

    if response.plan:
        response.plan.model_dump()  # ensure serialisable

    logger.info(
        "Planner response | session=%s | status=%s | confidence=%.2f | req_id=%s",
        session_id,
        response.status,
        response.plan.confidence_score if response.plan else 0.0,
        request_id,
    )
    return response


@router.post(
    "/clarify",
    response_model=PlannerResponse,
    summary="Answer a clarification question to complete planning",
    description=(
        "When /plan returns `status: needs_clarification`, submit the user's answer here. "
        "The planner will combine the original request + answer into a revised plan."
    ),
)
def clarify(body: ClarifyRequest, request: Request) -> PlannerResponse:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

    # Build combined request: original + clarification answer
    combined = f"{body.original_request}. Additional detail: {body.answer}"

    logger.info(
        "Clarification received | session=%s | answer=%.60s",
        body.session_id, body.answer,
    )

    # Get existing session history to provide context
    history = AIPlannerService.get_session_history(body.session_id)

    planner_req = PlannerRequest(
        request_text=combined,
        session_id=body.session_id,
        conversation_history=history,
    )

    response = AIPlannerService.plan(planner_req)
    response.request_id = request_id
    return response


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Get current session conversation history",
)
def get_session(session_id: str) -> SessionResponse:
    history = AIPlannerService.get_session_history(session_id)
    return SessionResponse(
        session_id=session_id,
        history=history,
        turn_count=len([m for m in history if m.get("role") == "user"]),
    )


@router.delete(
    "/session",
    status_code=204,
    summary="Clear session memory",
)
def clear_session(session_id: str) -> None:
    AIPlannerService.clear_session(session_id)
    logger.info("Session cleared | session_id=%s", session_id)
    return None


@router.get(
    "/schema",
    response_model=SchemaResponse,
    summary="Get the WorkflowPlan JSON schema",
    description="Returns the full JSON Schema for the WorkflowPlan output format.",
)
def get_schema() -> SchemaResponse:
    return SchemaResponse(
        json_schema=WorkflowPlan.model_json_schema(),
        description=(
            "WorkflowPlan is the complete output of the AI Planner. "
            "It contains the trigger, ordered steps, integrations, channels, "
            "confidence score, missing info, and plain-English explanation."
        ),
    )


@router.get(
    "/health",
    summary="AI Planner health check",
)
def planner_health() -> dict:
    from ..config import settings
    from ..services.ai_planner import _session_store

    ai_configured = bool(settings.ai_api_key) and settings.ai_api_key not in ("", "replace_me")
    stats = _session_store.stats()

    return {
        "status": "ok",
        "ai_configured": ai_configured,
        "model": settings.ai_model if ai_configured else "rule-based-fallback",
        "provider": settings.ai_base_url if ai_configured else "none",
        "session_store": stats,
        "capabilities": [
            "intent_analysis",
            "trigger_detection",
            "action_identification",
            "integration_detection",
            "missing_info_detection",
            "clarification_questions",
            "workflow_json_generation",
            "step_explanations",
            "confidence_scoring",
            "multi_turn_sessions",
        ],
    }
