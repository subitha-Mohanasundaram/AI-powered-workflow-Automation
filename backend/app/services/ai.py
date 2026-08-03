"""
AI Interpreter Service — powered by the OpenAI-compatible SDK.

Supports any OpenAI-compatible provider via AI_BASE_URL:
  - Groq  (default): https://api.groq.com/openai/v1
  - OpenAI:          https://api.openai.com/v1
  - OpenRouter:      https://openrouter.ai/api/v1

Flow:
  1. Validate that AI_API_KEY is set.
  2. Call the chat completions endpoint with a structured JSON prompt.
  3. Extract JSON from the response (handles both raw JSON and markdown fences).
  4. Parse and validate against WorkflowInstruction schema.
  5. On any failure (network, quota, bad JSON, schema mismatch) fall back
     to the rule-based heuristic so the API never returns an error to the user.

Token usage is logged on every successful call so you can monitor costs.
"""
import json
import re
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
from pydantic import BaseModel, ValidationError

from ..config import settings
from ..logging_config import get_logger
from ..schemas import WorkflowInstruction


# ── Clarification model ───────────────────────────────────────────────────────

class ClarificationQuestion(BaseModel):
    needs_clarification: bool
    question: str = ""
    partial_instruction: Optional[WorkflowInstruction] = None

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

# Providers that reliably support json_object response_format
_JSON_MODE_PROVIDERS = ("openai.com", "openrouter.ai")


def _get_client() -> OpenAI:
    """Return a cached OpenAI-compatible client, creating it on first use."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url.rstrip("/"),
            timeout=settings.ai_timeout_seconds,
            max_retries=2,
        )
        logger.info(
            "LLM client initialised | provider=%s | model=%s",
            settings.ai_base_url,
            settings.ai_model,
        )
    return _client


def _supports_json_mode() -> bool:
    """Return True if the configured provider supports response_format json_object."""
    return any(p in settings.ai_base_url for p in _JSON_MODE_PROVIDERS)


def _extract_json(text: str) -> str:
    """
    Extract a JSON object from a response string.
    Handles:
      - Raw JSON
      - JSON wrapped in ```json ... ``` markdown fences
      - JSON wrapped in ``` ... ``` fences
    """
    text = text.strip()
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    # Find the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)
    return text


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
                "Add a Groq key (console.groq.com/keys) or any OpenAI-compatible key to AI_API_KEY in .env."
            )
            return AIInterpreterService._fallback_instruction(request_text)

        try:
            return AIInterpreterService._call_openai(request_text)
        except AuthenticationError:
            logger.error(
                "LLM authentication failed — check AI_API_KEY in .env. "
                "Using rule-based fallback."
            )
        except RateLimitError:
            logger.error(
                "LLM rate limit exceeded — using rule-based fallback. "
                "Check your usage at the provider dashboard."
            )
        except APITimeoutError:
            logger.error(
                "LLM request timed out after %ds — using rule-based fallback.",
                settings.ai_timeout_seconds,
            )
        except APIConnectionError as exc:
            logger.error(
                "LLM connection error — using rule-based fallback | error=%s", exc
            )
        except APIStatusError as exc:
            logger.error(
                "LLM API error — using rule-based fallback | status=%d | body=%s",
                exc.status_code,
                exc.message,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            logger.error(
                "LLM response failed schema validation — using rule-based fallback | error=%s",
                exc,
            )
        except Exception as exc:
            logger.error(
                "Unexpected LLM error — using rule-based fallback | error=%s",
                exc,
                exc_info=True,
            )

        return AIInterpreterService._fallback_instruction(request_text)

    # ── LLM call ──────────────────────────────────────────────────────────────

    @staticmethod
    def _call_openai(request_text: str) -> WorkflowInstruction:
        """
        Call an OpenAI-compatible chat completions endpoint.
        Works with Groq, OpenAI, OpenRouter, and other compatible providers.
        Raises on any API or validation error — caller handles fallback.
        """
        client = _get_client()
        prompt_tokens = _count_tokens(_SYSTEM_PROMPT + request_text, settings.ai_model)
        logger.info(
            "Calling LLM | provider=%s | model=%s | ~prompt_tokens=%d",
            settings.ai_base_url,
            settings.ai_model,
            prompt_tokens,
        )

        # Build kwargs — only add response_format for providers that support it
        kwargs: dict = dict(
            model=settings.ai_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": request_text},
            ],
        )
        if _supports_json_mode():
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)

        # Log token usage for cost monitoring
        usage = response.usage
        if usage:
            logger.info(
                "LLM usage | model=%s | prompt_tokens=%d | completion_tokens=%d | total_tokens=%d",
                settings.ai_model,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("LLM returned an empty response")

        logger.debug("LLM raw response | length=%d | content=%s", len(raw_content), raw_content[:300])

        # Extract JSON — handles raw JSON and markdown-fenced responses
        json_str = _extract_json(raw_content)
        parsed = json.loads(json_str)
        instruction = WorkflowInstruction(**parsed)

        logger.info(
            "LLM interpretation successful | workflow=%s | steps=%d | channels=%s",
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

    # ── Clarification agent ───────────────────────────────────────────────────

    # Intent keywords used to compute confidence score
    _INTENT_KEYWORDS = [
        "fetch", "get", "retrieve", "pull",
        "report", "summary", "analytics", "analyze",
        "send", "email", "notify", "slack", "alert",
        "schedule", "daily", "weekly", "cron",
        "transform", "filter", "aggregate", "process",
        "dashboard", "update", "store",
    ]

    @staticmethod
    def _confidence_score(request_text: str) -> float:
        """
        Simple heuristic confidence score: count matched intent keywords / 10,
        capped at 1.0.
        """
        lower = request_text.lower()
        matched = sum(1 for kw in AIInterpreterService._INTENT_KEYWORDS if kw in lower)
        return min(matched / 10.0, 1.0)

    @staticmethod
    def check_clarification(request_text: str) -> ClarificationQuestion:
        """
        Check if the request needs clarification before execution.
        Returns ClarificationQuestion with needs_clarification=True if confidence < 0.5.
        """
        score = AIInterpreterService._confidence_score(request_text)
        logger.info("Confidence score | score=%.2f | request=%.60s...", score, request_text)

        if score < 0.5:
            question = AIInterpreterService._generate_clarification_question(request_text)
            return ClarificationQuestion(
                needs_clarification=True,
                question=question,
                partial_instruction=None,
            )

        # High enough confidence — attempt partial interpretation for context
        try:
            partial = AIInterpreterService._fallback_instruction(request_text)
            return ClarificationQuestion(
                needs_clarification=False,
                question="",
                partial_instruction=partial,
            )
        except Exception:
            return ClarificationQuestion(needs_clarification=False, question="")

    @staticmethod
    def _generate_clarification_question(request_text: str) -> str:
        """Generate a targeted clarification question for an ambiguous request."""
        lower = request_text.lower()

        if len(request_text.strip()) < 20:
            return ("Your request is quite brief. Could you describe what data you want "
                    "to fetch, what action to perform, and where to deliver results?")

        if not any(kw in lower for kw in ["email", "slack", "dashboard", "notify", "send"]):
            return ("Where should the results be delivered? "
                    "For example: email, Slack, or dashboard?")

        if not any(kw in lower for kw in ["fetch", "get", "report", "data", "analyze", "update"]):
            return ("What action should be performed? "
                    "For example: fetch data, generate a report, or send a notification?")

        return ("Could you provide more details about your automation request? "
                "Please specify the data source, the action to perform, and the delivery channel.")
