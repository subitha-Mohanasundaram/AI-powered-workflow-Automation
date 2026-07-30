"""
AI diagnostic and direct-interpretation endpoints.

GET  /api/ai/status    — check whether the OpenAI key is configured and reachable
POST /api/ai/interpret — interpret a request and return the raw WorkflowInstruction
                         (useful for debugging / previewing what the AI plans to do)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..logging_config import get_logger
from ..schemas import WorkflowInstruction
from ..security import require_api_key
from ..services.ai import AIInterpreterService, _get_client

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/ai",
    tags=["ai"],
    dependencies=[Depends(require_api_key)],
)


# ── Request / Response models ─────────────────────────────────────────────────

class AIInterpretRequest(BaseModel):
    request_text: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Plain-language automation request to interpret.",
        examples=["Fetch daily sales data and send a summary report to Slack and email"],
    )


class AIStatusResponse(BaseModel):
    configured: bool
    model: str
    base_url: str
    reachable: bool
    error: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Check OpenAI connectivity",
    description="Verifies the API key is set and makes a minimal API call to confirm the key is valid.",
)
def ai_status() -> AIStatusResponse:
    configured = bool(settings.ai_api_key) and settings.ai_api_key not in ("replace_me", "")
    if not configured:
        return AIStatusResponse(
            configured=False,
            model=settings.ai_model,
            base_url=settings.ai_base_url,
            reachable=False,
            error="AI_API_KEY is not set. Get a free Groq key at console.groq.com/keys and add it to .env",
        )

    # Make a minimal real API call to verify the key works
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.ai_model,
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}],
        )
        logger.info(
            "AI status check passed | model=%s | finish_reason=%s",
            settings.ai_model,
            response.choices[0].finish_reason,
        )
        return AIStatusResponse(
            configured=True,
            model=settings.ai_model,
            base_url=settings.ai_base_url,
            reachable=True,
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("AI status check failed | error=%s", error_msg)
        return AIStatusResponse(
            configured=True,
            model=settings.ai_model,
            base_url=settings.ai_base_url,
            reachable=False,
            error=error_msg,
        )


@router.post(
    "/interpret",
    response_model=WorkflowInstruction,
    summary="Interpret a request via OpenAI (preview)",
    description=(
        "Sends the request text to OpenAI and returns the structured WorkflowInstruction "
        "without executing or persisting anything. Useful for testing your prompt."
    ),
    openapi_extra={"security": [{"ApiKeyAuth": []}]},
)
def interpret(body: AIInterpretRequest) -> WorkflowInstruction:
    if not settings.ai_api_key or settings.ai_api_key in ("replace_me", ""):
        raise HTTPException(
            status_code=503,
            detail="AI_API_KEY is not configured. Set it in .env to use this endpoint.",
        )

    logger.info("Direct AI interpret request | text=%.80s...", body.request_text)
    instruction = AIInterpreterService.interpret_request(body.request_text)
    return instruction
