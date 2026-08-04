"""
Phase 3 — AI Planner Service

The full pipeline for converting natural language into an executable workflow:

  Stage 1 — Intent Analysis        : detect what the user wants
  Stage 2 — Gap Detection          : find missing information
  Stage 3 — Follow-up Questions    : ask for missing info if needed
  Stage 4 — Workflow Generation    : produce full WorkflowPlan JSON
  Stage 5 — Step Explanation       : explain each step in plain English
  Stage 6 — Confidence Scoring     : rate how well the intent was understood

Example input:
  "Every morning send weather and AI news to my email"

Example output:
  WorkflowPlan {
    confidence_score: 0.92,
    workflow_name: "morning_weather_and_news",
    trigger: {type: "schedule", cron: "0 7 * * *"},
    steps: [...],
    integrations: ["open-meteo", "hackernews"],
    missing_info: [],
    needs_clarification: False,
    explanation: "This workflow runs every morning at 7 AM...",
    ...
  }
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ..config import settings
from ..logging_config import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON SCHEMA — WorkflowPlan
# ═══════════════════════════════════════════════════════════════════════════════

class PlannerStep(BaseModel):
    """A single step in the planned workflow."""
    step_number: int
    name: str
    action: str
    integration: str = ""           # e.g. "open-meteo", "gmail", "slack"
    params: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""           # plain-English description of this step
    is_optional: bool = False
    depends_on: list[int] = Field(default_factory=list)  # step numbers this depends on

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip()[:100]

    @field_validator("depends_on", mode="before")
    @classmethod
    def coerce_depends_on(cls, v) -> list:
        """Accept depends_on as list of ints OR list of strings (LLM sometimes returns step names)."""
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, int):
                result.append(item)
            elif isinstance(item, str):
                # Try to parse as int; skip if it's a step name string
                try:
                    result.append(int(item))
                except ValueError:
                    pass  # ignore step-name references
        return result


class TriggerSpec(BaseModel):
    """How and when the workflow is triggered."""
    type: Literal["manual", "schedule", "webhook", "event"] = "manual"
    cron: Optional[str] = None          # "0 7 * * *" = 7 AM daily
    schedule_label: Optional[str] = None  # "Every morning at 7 AM"
    webhook_path: Optional[str] = None
    event_type: Optional[str] = None


class MissingField(BaseModel):
    """A piece of information the planner couldn't infer."""
    field: str                          # e.g. "recipient_email"
    reason: str                         # why it's needed
    question: str                       # what to ask the user
    can_proceed_without: bool = False   # whether execution can continue anyway


class WorkflowPlan(BaseModel):
    """
    Complete AI-generated workflow plan.
    This is the single output of the AI Planner for any natural language request.
    """
    # Identity
    workflow_name: str
    description: str = ""

    # Understanding
    intent_summary: str             # one-sentence summary of what was understood
    confidence_score: float         # 0.0 – 1.0
    confidence_label: str           # "high" | "medium" | "low"

    # Trigger
    trigger: TriggerSpec

    # Steps (ordered)
    steps: list[PlannerStep]

    # Integrations detected
    integrations: list[str] = Field(default_factory=list)

    # Delivery
    channels: list[str] = Field(default_factory=list)
    output_format: str = "text"

    # Gaps / clarification
    missing_info: list[MissingField] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None

    # Human-readable explanation
    explanation: str = ""           # full plain-English walkthrough

    # Metadata
    model_used: str = ""
    tokens_used: int = 0
    planning_time_ms: int = 0
    fallback_used: bool = False
    raw_llm_response: Optional[str] = None

    @field_validator("confidence_score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, round(v, 2)))

    @field_validator("workflow_name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        normalized = v.strip().lower().replace(" ", "_")
        return "".join(c for c in normalized if c.isalnum() or c in {"_", "-"})[:80] or "unnamed_workflow"


class PlannerRequest(BaseModel):
    """Input to the AI Planner."""
    request_text: str = Field(..., min_length=3, max_length=2000)
    conversation_history: list[dict] = Field(default_factory=list)  # prior turns
    user_context: dict = Field(default_factory=dict)                 # known user settings
    session_id: Optional[str] = None                                 # for multi-turn sessions


class PlannerResponse(BaseModel):
    """Full response from the AI Planner API endpoint."""
    status: Literal["complete", "needs_clarification", "error"]
    plan: Optional[WorkflowPlan] = None
    question: Optional[str] = None      # set when status == needs_clarification
    error_message: Optional[str] = None # set when status == error
    request_id: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════════

_PLANNER_SYSTEM_PROMPT = """You are an expert AI Workflow Automation Planner.

Your job is to analyze a user's natural language automation request and produce a
complete, executable workflow plan as a JSON object.

## YOUR ANALYSIS PROCESS

1. UNDERSTAND INTENT
   - What does the user ultimately want to achieve?
   - Is this a one-time task or recurring?

2. IDENTIFY TRIGGER
   - Does it have a schedule? ("every morning" → cron "0 7 * * *")
   - Is it manual (on-demand)?
   - Is it event-based (on form submission, on new email, etc.)?

3. IDENTIFY ACTIONS (in execution order)
   - What data needs to be fetched? From where?
   - What transformations are needed?
   - What reports or summaries to generate?
   - How should results be delivered?

4. IDENTIFY INTEGRATIONS
   Use ONLY these integration identifiers:
   - "open-meteo"      → weather data (free, no key needed)
   - "gnews"           → general news headlines
   - "hackernews"      → tech/AI news
   - "github"          → GitHub repository data
   - "open.er-api.com" → currency exchange rates
   - "gmail"           → send email via SMTP
   - "slack"           → Slack webhook notification
   - "dashboard"       → internal dashboard storage
   - "custom_url"      → user-provided API endpoint

5. DETECT MISSING INFORMATION
   - Is the recipient email address known? (if email delivery requested)
   - Is the city known? (if weather requested)
   - Is the GitHub repo known? (if GitHub data requested)
   - Is a Slack webhook URL configured? (if Slack delivery requested)

6. SCORE YOUR CONFIDENCE (0.0 to 1.0)
   - 0.9–1.0: All information present, clear intent
   - 0.7–0.89: Intent clear, minor details can be inferred
   - 0.5–0.69: Intent understood but key details missing
   - Below 0.5: Request is too ambiguous to proceed

7. IF CONFIDENCE < 0.7: identify the single most important missing piece and
   return a targeted follow-up question.

## ALLOWED STEP ACTIONS
api_fetch, transform_data, report_generation, email_send, slack_notify,
dashboard_update, notification_send

## CRON REFERENCE
- "every morning" / "daily at 7am"  → "0 7 * * *"
- "every Monday"                    → "0 8 * * 1"
- "every hour"                      → "0 * * * *"
- "every 30 minutes"                → "*/30 * * * *"
- "every weekday"                   → "0 8 * * 1-5"
- "twice a day"                     → "0 8,18 * * *"

## OUTPUT FORMAT
Return ONLY a valid JSON object — no markdown fences, no prose outside the JSON.

{
  "workflow_name": "<snake_case, 3-80 chars>",
  "description": "<one sentence>",
  "intent_summary": "<what you understood in one sentence>",
  "confidence_score": <0.0-1.0>,
  "confidence_label": "<high|medium|low>",
  "trigger": {
    "type": "<manual|schedule|webhook|event>",
    "cron": "<cron expression or null>",
    "schedule_label": "<human readable or null>"
  },
  "steps": [
    {
      "step_number": 1,
      "name": "<step name>",
      "action": "<action>",
      "integration": "<integration id>",
      "params": {},
      "explanation": "<plain English: what this step does and why>",
      "is_optional": false,
      "depends_on": []
    }
  ],
  "integrations": ["<integration ids used>"],
  "channels": ["<dashboard|email|slack>"],
  "output_format": "<text|json|html|markdown>",
  "missing_info": [
    {
      "field": "<field name>",
      "reason": "<why it's needed>",
      "question": "<what to ask the user>",
      "can_proceed_without": false
    }
  ],
  "needs_clarification": <true|false>,
  "clarification_question": "<single most important question or null>",
  "explanation": "<full plain-English walkthrough of the entire workflow>"
}"""

_CLARIFICATION_SYSTEM_PROMPT = """You are a helpful AI assistant.
A user described an automation task but was missing some details.
Ask ONE clear, concise follow-up question to get the most important missing information.
Be friendly and specific. Maximum 2 sentences."""


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY / SESSION STORE  (in-process, TTL-based)
# ═══════════════════════════════════════════════════════════════════════════════

import threading

_SESSION_TTL_SECONDS = 600  # 10 minutes


class _PlannerSessionStore:
    """
    Lightweight in-memory store for multi-turn planner conversations.
    Each session_id maps to a list of message dicts + metadata.
    Expired sessions are pruned on each write.
    """
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> list[dict]:
        with self._lock:
            entry = self._store.get(session_id)
            if not entry:
                return []
            if time.time() - entry["last_active"] > _SESSION_TTL_SECONDS:
                del self._store[session_id]
                return []
            return list(entry["messages"])

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self._prune_expired()
            if session_id not in self._store:
                self._store[session_id] = {"messages": [], "last_active": time.time()}
            self._store[session_id]["messages"].append({"role": role, "content": content})
            self._store[session_id]["last_active"] = time.time()
            # Keep only last 10 turns to limit token usage
            self._store[session_id]["messages"] = self._store[session_id]["messages"][-20:]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def _prune_expired(self):
        now = time.time()
        expired = [sid for sid, v in self._store.items()
                   if now - v["last_active"] > _SESSION_TTL_SECONDS]
        for sid in expired:
            del self._store[sid]

    def stats(self) -> dict:
        with self._lock:
            return {"active_sessions": len(self._store)}


_session_store = _PlannerSessionStore()


# ═══════════════════════════════════════════════════════════════════════════════
# RULE-BASED FALLBACK PLANNER
# ═══════════════════════════════════════════════════════════════════════════════

_SCHEDULE_PATTERNS: list[tuple[list[str], str, str]] = [
    (["every morning", "each morning", "daily morning", "morning"],    "0 7 * * *",   "Every morning at 7 AM"),
    (["every evening", "each evening"],                                 "0 18 * * *",  "Every evening at 6 PM"),
    (["every day", "daily", "each day", "once a day"],                  "0 8 * * *",   "Every day at 8 AM"),
    (["every hour", "hourly", "each hour"],                             "0 * * * *",   "Every hour"),
    (["every 30 min", "every thirty", "half hour"],                     "*/30 * * * *","Every 30 minutes"),
    (["every monday", "weekly", "once a week"],                         "0 8 * * 1",   "Every Monday at 8 AM"),
    (["every weekday", "working day", "mon-fri"],                       "0 8 * * 1-5", "Every weekday at 8 AM"),
    (["every night", "nightly", "at night", "midnight"],                "0 0 * * *",   "Every day at midnight"),
    (["every sunday"],                                                   "0 8 * * 0",   "Every Sunday at 8 AM"),
    (["every friday"],                                                   "0 8 * * 5",   "Every Friday at 8 AM"),
    (["twice a day"],                                                    "0 8,18 * * *","Twice daily (8 AM and 6 PM)"),
]

_INTEGRATION_PATTERNS: dict[str, list[str]] = {
    "open-meteo":      ["weather", "temperature", "forecast", "rain", "humidity", "wind", "climate"],
    "gnews":           ["news", "headlines", "articles", "latest news"],
    "hackernews":      ["tech news", "ai news", "hacker news", "technology news", "startup news"],
    "github":          ["github", "repository", "repo", "commits", "pull request", "stars", "code"],
    "open.er-api.com": ["currency", "exchange rate", "forex", "usd", "eur", "inr", "conversion"],
    "gmail":           ["email", "mail", "send to", "my inbox"],
    "slack":           ["slack", "channel", "workspace"],
    "dashboard":       ["dashboard", "store", "save", "display"],
}

_MISSING_INFO_RULES: list[tuple[str, list[str], str, str, str, bool]] = [
    # (field, trigger_keywords, reason, question, can_proceed_without)
    ("recipient_email", ["email", "mail", "send to my email"],
     "Email recipient is needed for delivery",
     "What email address should the results be sent to?",
     "email_send", False),
    ("city", ["weather", "temperature", "forecast"],
     "City or location is needed to fetch weather",
     "Which city or location should I fetch the weather for?",
     "api_fetch", False),
    ("github_repo", ["github", "repository", "repo", "commits"],
     "GitHub repository name is needed",
     "Which GitHub repository? (format: owner/repo, e.g. microsoft/vscode)",
     "api_fetch", False),
    ("news_topic", ["news", "headlines"],
     "A topic makes news more relevant",
     "Any specific topic for the news? (e.g. AI, technology, finance) — or leave blank for top headlines.",
     "api_fetch", True),
    ("slack_channel", ["slack"],
     "Slack webhook URL is needed for Slack delivery",
     "Please provide your Slack webhook URL to enable Slack delivery.",
     "slack_notify", False),
    ("base_currency", ["exchange rate", "currency", "forex"],
     "Base currency is needed for exchange rate lookup",
     "Which base currency? (e.g. USD, EUR, GBP)",
     "api_fetch", False),
]


def _detect_trigger_fallback(text: str) -> TriggerSpec:
    """Detect trigger type and cron from natural language."""
    lower = text.lower()
    for keywords, cron, label in _SCHEDULE_PATTERNS:
        if any(kw in lower for kw in keywords):
            return TriggerSpec(type="schedule", cron=cron, schedule_label=label)
    return TriggerSpec(type="manual")


def _detect_integrations_fallback(text: str) -> list[str]:
    lower = text.lower()
    return [integ for integ, kws in _INTEGRATION_PATTERNS.items()
            if any(kw in lower for kw in kws)]


def _detect_channels_fallback(text: str) -> list[str]:
    lower = text.lower()
    channels = []
    if "email" in lower or "mail" in lower:
        channels.append("email")
    if "slack" in lower:
        channels.append("slack")
    if not channels or "dashboard" in lower:
        channels.append("dashboard")
    return list(dict.fromkeys(channels))  # deduplicate, preserve order


def _detect_missing_info(text: str, integrations: list[str], channels: list[str]) -> list[MissingField]:
    lower = text.lower()
    missing = []
    for field, trigger_kws, reason, question, _, can_proceed in _MISSING_INFO_RULES:
        if any(kw in lower for kw in trigger_kws):
            # Check if info might already be in the request
            if field == "recipient_email" and ("email" in channels) and "@" not in text:
                missing.append(MissingField(field=field, reason=reason,
                                            question=question, can_proceed_without=can_proceed))
            elif field == "city" and "open-meteo" in integrations:
                city_hints = ["for ", "in ", "at "]
                if not any(hint in lower for hint in city_hints):
                    missing.append(MissingField(field=field, reason=reason,
                                                question=question, can_proceed_without=can_proceed))
            elif field == "github_repo" and "github" in integrations:
                if "/" not in text:
                    missing.append(MissingField(field=field, reason=reason,
                                                question=question, can_proceed_without=can_proceed))
            elif field == "slack_channel" and "slack" in channels:
                missing.append(MissingField(field=field, reason=reason,
                                            question=question, can_proceed_without=True))
            elif field == "base_currency" and "open.er-api.com" in integrations:
                currencies = ["usd", "eur", "gbp", "inr", "jpy"]
                if not any(c in lower for c in currencies):
                    missing.append(MissingField(field=field, reason=reason,
                                                question=question, can_proceed_without=can_proceed))
    return missing


def _build_steps_fallback(text: str, integrations: list[str], channels: list[str]) -> list[PlannerStep]:
    lower = text.lower()
    steps = []
    n = 1

    # Step 1: Fetch data
    for integ in integrations:
        if integ not in ("gmail", "slack", "dashboard"):
            params = {}
            if integ == "open-meteo":
                # Try to extract city
                m = re.search(r"(?:for|in|at)\s+([A-Za-z\s]+?)(?:\s+and|\s+every|\s+send|$)", text, re.I)
                params["city"] = m.group(1).strip() if m else "Chennai"
            elif integ == "github":
                m = re.search(r"([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", text)
                params["repo"] = m.group(1) if m else ""
            elif integ in ("gnews", "hackernews"):
                topic_match = re.search(r"(ai|tech|finance|sports|health|science|business)", lower)
                params["topic"] = topic_match.group(1) if topic_match else "technology"
            elif integ == "open.er-api.com":
                curr_match = re.search(r"\b(USD|EUR|GBP|INR|JPY|AUD|CAD)\b", text, re.I)
                params["base_currency"] = curr_match.group(1).upper() if curr_match else "USD"

            steps.append(PlannerStep(
                step_number=n, name=f"fetch_{integ.replace('.', '_').replace('-', '_')}",
                action="api_fetch", integration=integ, params=params,
                explanation=f"Fetch data from {integ}."
            ))
            n += 1

    # Step 2: Transform if needed
    if any(kw in lower for kw in ["filter", "combine", "merge", "aggregate", "process", "transform"]):
        steps.append(PlannerStep(
            step_number=n, name="transform_data", action="transform_data",
            explanation="Process and combine the fetched data.", params={}
        ))
        n += 1

    # Step 3: Generate report/summary if asked
    if any(kw in lower for kw in ["report", "summary", "digest", "newsletter"]):
        steps.append(PlannerStep(
            step_number=n, name="generate_report", action="report_generation",
            explanation="Compile data into a readable report.", params={}
        ))
        n += 1

    # Step 4+: Deliver to channels
    for channel in channels:
        if channel == "email":
            m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]+", text)
            params = {"recipient": m.group(0) if m else ""}
            steps.append(PlannerStep(
                step_number=n, name="send_email", action="email_send",
                integration="gmail", params=params,
                explanation=f"Send results to {params.get('recipient', 'configured email address')}."
            ))
            n += 1
        elif channel == "slack":
            steps.append(PlannerStep(
                step_number=n, name="notify_slack", action="slack_notify",
                integration="slack", params={},
                explanation="Post a summary to the configured Slack channel."
            ))
            n += 1
        elif channel == "dashboard":
            steps.append(PlannerStep(
                step_number=n, name="update_dashboard", action="dashboard_update",
                integration="dashboard", params={},
                explanation="Store results in the automation dashboard."
            ))
            n += 1

    if not steps:
        steps.append(PlannerStep(
            step_number=1, name="fetch_data", action="api_fetch",
            explanation="Fetch the requested data."
        ))
    return steps


def _confidence_score_heuristic(text: str, steps: list[PlannerStep],
                                 missing: list[MissingField]) -> float:
    """Score based on: steps found + integrations known + missing blockers."""
    score = 0.5  # base

    # More steps detected → better understanding
    score += min(len(steps) * 0.1, 0.3)

    # Non-blocking missing info → small penalty
    blockers = [m for m in missing if not m.can_proceed_without]
    score -= len(blockers) * 0.15

    # Optional missing → very small penalty
    optional_missing = [m for m in missing if m.can_proceed_without]
    score -= len(optional_missing) * 0.05

    return max(0.0, min(1.0, round(score, 2)))


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _build_explanation(plan_data: dict) -> str:
    """Generate a plain-English walkthrough of the workflow."""
    parts = []
    wf = plan_data.get("workflow_name", "").replace("_", " ")
    trigger = plan_data.get("trigger", {})
    steps = plan_data.get("steps", [])
    channels = plan_data.get("channels", [])
    missing = plan_data.get("missing_info", [])

    if trigger.get("type") == "schedule" and trigger.get("schedule_label"):
        parts.append(f"This workflow will run automatically — {trigger['schedule_label'].lower()}.")
    else:
        parts.append("This workflow will run when manually triggered.")

    if steps:
        parts.append(f"It will execute {len(steps)} step(s):")
        for s in steps:
            if isinstance(s, dict):
                expl = s.get("explanation") or f"Step {s.get('step_number')}: {s.get('action')}"
            else:
                expl = s.explanation or f"Step {s.step_number}: {s.action}"
            parts.append(f"  • {expl}")

    if channels:
        parts.append(f"Results will be delivered to: {', '.join(channels)}.")

    if missing:
        blockers = [m["question"] if isinstance(m, dict) else m.question
                    for m in missing if not (m["can_proceed_without"] if isinstance(m, dict) else m.can_proceed_without)]
        if blockers:
            parts.append(f"Still needs: {'; '.join(blockers)}")

    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AI PLANNER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class AIPlannerService:
    """
    The central AI Planner. Converts natural language → WorkflowPlan.

    Flow:
      1. Try full LLM planning (Groq/OpenAI)
      2. Parse and validate the structured JSON response
      3. If LLM unavailable or fails → rule-based fallback
      4. Assess confidence and determine if clarification is needed
      5. Store conversation turn in session memory
    """

    # ── Public entry point ────────────────────────────────────────────────────

    @staticmethod
    def plan(req: PlannerRequest) -> PlannerResponse:
        """
        Main entry point.  Takes a PlannerRequest, returns a PlannerResponse.
        Never raises — always returns a usable response.
        """
        import uuid
        request_id = str(uuid.uuid4())[:8]
        start_ms = int(time.time() * 1000)

        # Persist user turn in session memory
        if req.session_id:
            _session_store.append(req.session_id, "user", req.request_text)

        try:
            if settings.ai_api_key and settings.ai_api_key not in ("", "replace_me"):
                plan = AIPlannerService._plan_with_llm(req)
            else:
                logger.warning("AI_API_KEY not set — using rule-based planner")
                plan = AIPlannerService._plan_with_rules(req.request_text)
                plan.fallback_used = True

            plan.planning_time_ms = int(time.time() * 1000) - start_ms
            plan.model_used = settings.ai_model if not plan.fallback_used else "rule-based"

            # Persist assistant response in session memory
            if req.session_id:
                _session_store.append(req.session_id, "assistant",
                                      f"Plan: {plan.workflow_name} | confidence: {plan.confidence_score}")

            status = "needs_clarification" if plan.needs_clarification else "complete"
            return PlannerResponse(
                status=status,
                plan=plan,
                question=plan.clarification_question if plan.needs_clarification else None,
                request_id=request_id,
            )

        except Exception as exc:
            logger.error("AI Planner error | error=%s", exc, exc_info=True)
            return PlannerResponse(
                status="error",
                error_message=f"Planning failed: {str(exc)[:200]}",
                request_id=request_id,
            )

    # ── LLM-based planning ────────────────────────────────────────────────────

    @staticmethod
    def _plan_with_llm(req: PlannerRequest) -> WorkflowPlan:
        """Call the LLM with the full planner prompt and parse the response."""
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url.rstrip("/"),
            timeout=settings.ai_timeout_seconds,
            max_retries=2,
        )

        # Build message list — include session history for multi-turn
        messages = [{"role": "system", "content": _PLANNER_SYSTEM_PROMPT}]

        # Add conversation history from session
        history = req.conversation_history
        if req.session_id and not history:
            history = _session_store.get(req.session_id)

        for turn in history[-6:]:  # max 3 prior turns (6 messages)
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Add user context if provided
        user_ctx_note = ""
        if req.user_context:
            relevant = {k: v for k, v in req.user_context.items()
                        if k in ("email", "city", "timezone", "slack_configured")
                        and v}
            if relevant:
                user_ctx_note = f"\n\nKnown user settings: {json.dumps(relevant)}"

        messages.append({
            "role": "user",
            "content": req.request_text + user_ctx_note
        })

        # Build kwargs — json_object mode only for providers that support it
        kwargs: dict = dict(
            model=settings.ai_model,
            temperature=0.15,
            messages=messages,
        )
        from .ai import _supports_json_mode
        if _supports_json_mode():
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)

        usage = response.usage
        tokens_used = usage.total_tokens if usage else 0

        raw = response.choices[0].message.content or ""
        logger.debug("Planner LLM raw | length=%d | preview=%.200s", len(raw), raw)

        # Extract and parse JSON — with aggressive repair for Groq quirks
        from .ai import _extract_json
        json_str = _extract_json(raw)
        try:
            data = AIPlannerService._safe_json_parse(json_str)
        except ValueError as json_err:
            logger.warning("LLM JSON parse failed, using rule-based fallback | error=%s", json_err)
            plan = AIPlannerService._plan_with_rules(req.request_text)
            plan.fallback_used = True
            plan.tokens_used = tokens_used
            plan.raw_llm_response = raw[:500]
            return plan

        plan = AIPlannerService._parse_llm_response(data, raw)
        plan.tokens_used = tokens_used
        logger.info(
            "LLM plan generated | workflow=%s | confidence=%.2f | steps=%d | missing=%d",
            plan.workflow_name, plan.confidence_score, len(plan.steps), len(plan.missing_info)
        )
        return plan

    @staticmethod
    def _safe_json_parse(text: str) -> dict:
        """
        Parse JSON with fallback repairs for common LLM output issues:
        - Unescaped newlines/quotes inside string values
        - Trailing commas
        - Single quotes instead of double quotes
        - depends_on containing strings instead of ints
        """
        # Attempt 1: direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Attempt 2: strip trailing commas before } or ]
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Attempt 3: replace single quotes with double quotes (crude but effective)
        try:
            repaired2 = repaired.replace("'", '"')
            return json.loads(repaired2)
        except json.JSONDecodeError:
            pass

        # Attempt 4: extract just the outer object and re-parse key by key
        # Find the outermost { } and try to fix unescaped chars inside string values
        try:
            # Remove control characters except \n\t inside strings
            cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', repaired)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON repair failed: {e}") from e

    # ── Parse LLM JSON response → WorkflowPlan ────────────────────────────────

    @staticmethod
    def _parse_llm_response(data: dict, raw: str = "") -> WorkflowPlan:
        """Parse and validate LLM output into a WorkflowPlan."""

        # Parse trigger
        trigger_data = data.get("trigger", {})
        trigger = TriggerSpec(
            type=trigger_data.get("type", "manual"),
            cron=trigger_data.get("cron"),
            schedule_label=trigger_data.get("schedule_label"),
            webhook_path=trigger_data.get("webhook_path"),
            event_type=trigger_data.get("event_type"),
        )

        # Parse steps
        steps = []
        for s in data.get("steps", []):
            try:
                steps.append(PlannerStep(
                    step_number=s.get("step_number", len(steps) + 1),
                    name=s.get("name", "step"),
                    action=s.get("action", "api_fetch"),
                    integration=s.get("integration") or "",
                    params=s.get("params") or {},
                    explanation=s.get("explanation", ""),
                    is_optional=s.get("is_optional", False),
                    depends_on=s.get("depends_on") or [],
                ))
            except Exception as exc:
                logger.warning("Skipping malformed step | error=%s", exc)

        # Parse missing info
        missing = []
        for m in data.get("missing_info", []):
            try:
                missing.append(MissingField(
                    field=m.get("field", "unknown"),
                    reason=m.get("reason", ""),
                    question=m.get("question", ""),
                    can_proceed_without=m.get("can_proceed_without", False),
                ))
            except Exception:
                pass

        # Confidence
        raw_score = float(data.get("confidence_score", 0.7))
        score = max(0.0, min(1.0, round(raw_score, 2)))
        label = data.get("confidence_label") or _confidence_label(score)

        # Needs clarification
        needs_clarification = data.get("needs_clarification", score < 0.7)
        clarification_q = data.get("clarification_question")
        if needs_clarification and not clarification_q and missing:
            blockers = [m for m in missing if not m.can_proceed_without]
            clarification_q = blockers[0].question if blockers else missing[0].question

        # Explanation — use LLM's if provided, else build one
        explanation = data.get("explanation", "")
        if not explanation:
            explanation = _build_explanation(data)

        return WorkflowPlan(
            workflow_name=data.get("workflow_name", "unnamed_workflow"),
            description=data.get("description", ""),
            intent_summary=data.get("intent_summary", ""),
            confidence_score=score,
            confidence_label=label,
            trigger=trigger,
            steps=steps if steps else [PlannerStep(step_number=1, name="fetch_data",
                                                    action="api_fetch", explanation="Fetch data.")],
            integrations=data.get("integrations", []),
            channels=data.get("channels", ["dashboard"]),
            output_format=data.get("output_format", "text"),
            missing_info=missing,
            needs_clarification=needs_clarification,
            clarification_question=clarification_q,
            explanation=explanation,
            raw_llm_response=raw[:1000] if raw else None,
        )

    # ── Rule-based fallback planner ───────────────────────────────────────────

    @staticmethod
    def _plan_with_rules(text: str) -> WorkflowPlan:
        """Full rule-based planner — no LLM required."""
        trigger = _detect_trigger_fallback(text)
        integrations = _detect_integrations_fallback(text)
        channels = _detect_channels_fallback(text)
        steps = _build_steps_fallback(text, integrations, channels)
        missing = _detect_missing_info(text, integrations, channels)

        score = _confidence_score_heuristic(text, steps, missing)
        label = _confidence_label(score)

        # Pick workflow name from detected integrations
        parts = []
        if "open-meteo" in integrations:
            parts.append("weather")
        if "gnews" in integrations or "hackernews" in integrations:
            parts.append("news")
        if "github" in integrations:
            parts.append("github")
        if "open.er-api.com" in integrations:
            parts.append("currency")
        if not parts:
            parts.append("automation")
        if trigger.type == "schedule":
            parts.append("schedule")
        workflow_name = "_".join(parts)

        blockers = [m for m in missing if not m.can_proceed_without]
        needs_clarification = (score < 0.7) or bool(blockers)
        clarification_q = blockers[0].question if blockers else (
            missing[0].question if missing else None
        )

        data_for_explanation = {
            "workflow_name": workflow_name,
            "trigger": {"type": trigger.type, "schedule_label": trigger.schedule_label},
            "steps": [s.model_dump() for s in steps],
            "channels": channels,
            "missing_info": [m.model_dump() for m in missing],
        }

        return WorkflowPlan(
            workflow_name=workflow_name,
            description=f"Automated workflow: {workflow_name.replace('_', ' ')}",
            intent_summary=f"Automated task involving {', '.join(integrations) if integrations else 'custom automation'}",
            confidence_score=score,
            confidence_label=label,
            trigger=trigger,
            steps=steps,
            integrations=integrations,
            channels=channels,
            output_format="text",
            missing_info=missing,
            needs_clarification=needs_clarification,
            clarification_question=clarification_q,
            explanation=_build_explanation(data_for_explanation),
            fallback_used=True,
        )

    # ── Session helpers ───────────────────────────────────────────────────────

    @staticmethod
    def get_session_history(session_id: str) -> list[dict]:
        return _session_store.get(session_id)

    @staticmethod
    def clear_session(session_id: str) -> None:
        _session_store.clear(session_id)

    @staticmethod
    def session_stats() -> dict:
        return _session_store.stats()
