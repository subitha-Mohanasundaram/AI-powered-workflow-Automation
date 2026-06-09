"""
AI Interpreter Service — powered by the official OpenAI Python SDK.

Flow:
  1. Validate that AI_API_KEY is set.
  2. Call OpenAI chat completions with a structured JSON-mode prompt.
  3. Parse and validate the response against WorkflowInstruction schema.
  4. On any failure (network, quota, bad JSON, schema mismatch) fall back
     to the rule-based heuristic so the API never returns an error to the user.

Token usage is logged on every successful call so you can monitor costs.
"""
import json
from typing import Optional

import tiktoken
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError

from ..config import settings
from ..logging_config import get_logger
from ..schemas import WorkflowInstruction

logger = get_logger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an automation workflow planner. Your job is to convert a user's
plain-language automation request into a strictly structured JSON workflow definition.

Return ONLY a valid JSON object — no markdown fences, no explanation text.

Required JSON structure:
{
  "workflow_name": "<snake_case name, 3-80 chars>",
  "trigger": {"type": "manual", "source": "api"},
  "steps": [
    {"name": "<step name>", "action": "<action>", "params": {}}
  ],
  "channels": ["<channel>"],
  "output_format": "<format>"
}

Allowed actions (use ONLY these):
  api_fetch, transform_data, report_generation,
  email_send, slack_notify, dashboard_update, notification_send

Allowed channels (use ONLY these):
  dashboard, email, slack

Allowed output_format values:
  text, json, html, markdown

Rules:
- workflow_name must be lowercase, snake_case, 3–80 characters.
- steps must have at least 1 item.
- channels must have at least 1 item.
- Infer channels from the user's request (mention of "email" → include "email", etc.).
- Always include "dashboard" as a channel unless the user explicitly says not to.
- Use "api_fetch" as the first step when data retrieval is implied.
- Use "report_generation" when the user asks for reports, summaries, or analytics.
- Use "transform_data" when filtering, aggregating, or reshaping data is needed.
- Add delivery steps (email_send / slack_notify / dashboard_update) matching channels.
"""


# ── Client factory (singleton per process) ───────────────────────────────────
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI client, creating it on first use."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url.rstrip("/"),
            timeout=settings.ai_timeout_seconds,
            max_retries=2,          # SDK-level auto-retry on transient errors
        )
        logger.info(
            "OpenAI client initialised | base_url=%s | model=%s",
            settings.ai_base_url,
            settings.ai_model,
        )
    return _client


def _count_tokens(text: str, model: str) -> int:
    """Return approximate token count for a string (used for cost logging)."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


# ── Main service class ────────────────────────────────────────────────────────

class AIInterpreterService:

    @staticmethod
    def interpret_request(request_text: str) -> WorkflowInstruction:
        """
        Convert a plain-language automation request to a WorkflowInstruction.

        Always returns a valid WorkflowInstruction — never raises.
        When AI_API_KEY is missing or the API call fails, falls back to
        rule-based interpretation and logs the reason.
        """
        if not settings.ai_api_key or settings.ai_api_key in ("replace_me", ""):
            logger.warning(
                "AI_API_KEY not configured — rule-based fallback active. "
                "Add a real key to AI_API_KEY in .env to enable GPT interpretation."
            )
            return AIInterpreterService._fallback_instruction(request_text)

        try:
            return AIInterpreterService._call_openai(request_text)
        except AuthenticationError:
            logger.error(
                "OpenAI authentication failed — check AI_API_KEY in .env. "
                "Using rule-based fallback."
            )
        except RateLimitError:
            logger.error(
                "OpenAI rate limit exceeded — using rule-based fallback. "
                "Check your usage at platform.openai.com/usage"
            )
        except APITimeoutError:
            logger.error(
                "OpenAI request timed out after %ds — using rule-based fallback.",
                settings.ai_timeout_seconds,
            )
        except APIConnectionError as exc:
            logger.error(
                "OpenAI connection error — using rule-based fallback | error=%s", exc
            )
        except APIStatusError as exc:
            logger.error(
                "OpenAI API error — using rule-based fallback | status=%d | body=%s",
                exc.status_code,
                exc.message,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            logger.error(
                "OpenAI response failed schema validation — using rule-based fallback | error=%s",
                exc,
            )
        except Exception as exc:
            logger.error(
                "Unexpected OpenAI error — using rule-based fallback | error=%s",
                exc,
                exc_info=True,
            )

        return AIInterpreterService._fallback_instruction(request_text)

    # ── OpenAI call ───────────────────────────────────────────────────────────

    @staticmethod
    def _call_openai(request_text: str) -> WorkflowInstruction:
        """
        Call OpenAI chat completions API using the official SDK.
        Raises on any API or validation error — caller handles fallback.
        """
        client = _get_client()
        prompt_tokens = _count_tokens(_SYSTEM_PROMPT + request_text, settings.ai_model)
        logger.info(
            "Calling OpenAI | model=%s | ~prompt_tokens=%d",
            settings.ai_model,
            prompt_tokens,
        )

        response = client.chat.completions.create(
            model=settings.ai_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": request_text},
            ],
        )

        # Log token usage for cost monitoring
        usage = response.usage
        if usage:
            logger.info(
                "OpenAI usage | model=%s | prompt_tokens=%d | completion_tokens=%d | total_tokens=%d",
                settings.ai_model,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("OpenAI returned an empty response content")

        logger.debug("OpenAI raw response | length=%d | content=%s", len(raw_content), raw_content[:300])

        parsed = json.loads(raw_content)
        instruction = WorkflowInstruction(**parsed)

        logger.info(
            "OpenAI interpretation successful | workflow=%s | steps=%d | channels=%s",
            instruction.workflow_name,
            len(instruction.steps),
            instruction.channels,
        )
        return instruction

    # ── Rule-based fallback ───────────────────────────────────────────────────

    @staticmethod
    def _fallback_instruction(request_text: str) -> WorkflowInstruction:
        """
        Rule-based fallback used when OpenAI is unavailable.
        Infers channels and steps from keywords in the request text.
        """
        logger.info("Using rule-based fallback for request: %.80s...", request_text)
        channels = AIInterpreterService._infer_channels(request_text)
        steps: list[dict] = [{"name": "fetch_data", "action": "api_fetch", "params": {}}]

        lower = request_text.lower()
        if "report" in lower or "summary" in lower or "analytic" in lower:
            steps.append({"name": "generate_report", "action": "report_generation", "params": {}})
        if "transform" in lower or "process" in lower or "filter" in lower:
            steps.append({"name": "transform_data", "action": "transform_data", "params": {}})
        if "email" in channels:
            steps.append({"name": "send_email", "action": "email_send", "params": {}})
        if "slack" in channels:
            steps.append({"name": "notify_slack", "action": "slack_notify", "params": {}})
        if "dashboard" in channels:
            steps.append({"name": "update_dashboard", "action": "dashboard_update", "params": {}})

        return WorkflowInstruction(
            workflow_name="generic_automation",
            trigger={"type": "manual", "source": "api"},
            steps=steps,
            channels=channels,
            output_format="text",
        )

    @staticmethod
    def _infer_channels(request_text: str) -> list[str]:
        text = request_text.lower()
        channels: list[str] = []
        if "email" in text or "mail" in text:
            channels.append("email")
        if "slack" in text:
            channels.append("slack")
        if "dashboard" in text or not channels:
            # Always default to dashboard if no channel mentioned
            channels.append("dashboard")
        return channels
