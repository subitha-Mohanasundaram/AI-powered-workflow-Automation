"""
Unit tests for the OpenAI-powered AIInterpreterService.

All OpenAI SDK calls are mocked — no real API key needed to run these tests.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.config import settings
from backend.app.schemas import WorkflowInstruction
from backend.app.services.ai import AIInterpreterService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_openai_response(content: dict) -> MagicMock:
    """Build a mock that looks like an openai.types.chat.ChatCompletion object."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(content)
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage.prompt_tokens = 120
    mock_response.usage.completion_tokens = 80
    mock_response.usage.total_tokens = 200
    return mock_response


_VALID_OPENAI_PAYLOAD = {
    "workflow_name": "daily_sales_report",
    "trigger": {"type": "manual", "source": "api"},
    "steps": [
        {"name": "fetch_sales_data", "action": "api_fetch", "params": {}},
        {"name": "generate_report", "action": "report_generation", "params": {}},
        {"name": "send_email", "action": "email_send", "params": {}},
        {"name": "notify_slack", "action": "slack_notify", "params": {}},
    ],
    "channels": ["email", "slack", "dashboard"],
    "output_format": "html",
}


# ── Tests: happy path ─────────────────────────────────────────────────────────

class TestOpenAIIntegration:

    def test_successful_openai_call_returns_instruction(self, monkeypatch):
        """When OpenAI returns valid JSON, it parses into a WorkflowInstruction."""
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")
        mock_response = _make_openai_response(_VALID_OPENAI_PAYLOAD)

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = AIInterpreterService.interpret_request(
                "Fetch daily sales data and send a report to email and Slack"
            )

        assert isinstance(result, WorkflowInstruction)
        assert result.workflow_name == "daily_sales_report"
        assert len(result.steps) == 4
        assert "email" in result.channels
        assert "slack" in result.channels
        assert result.output_format == "html"

    def test_openai_logs_token_usage(self, monkeypatch, caplog):
        """Token usage from the API response is logged for cost monitoring."""
        import logging
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")
        mock_response = _make_openai_response(_VALID_OPENAI_PAYLOAD)

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            with caplog.at_level(logging.INFO, logger="backend.app.services.ai"):
                AIInterpreterService.interpret_request("Fetch data and email report")

        assert "total_tokens=200" in caplog.text

    def test_openai_call_uses_correct_model(self, monkeypatch):
        """The SDK is called with the model specified in settings."""
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")
        monkeypatch.setattr(settings, "ai_model", "gpt-4o-mini")
        mock_response = _make_openai_response(_VALID_OPENAI_PAYLOAD)

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            AIInterpreterService.interpret_request("Do something useful with data")

            call_kwargs = mock_client.chat.completions.create.call_args
            assert call_kwargs.kwargs["model"] == "gpt-4o-mini"

    def test_json_mode_is_requested(self, monkeypatch):
        """response_format json_object is always passed to prevent markdown wrapping."""
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")
        mock_response = _make_openai_response(_VALID_OPENAI_PAYLOAD)

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            AIInterpreterService.interpret_request("Automate my reporting workflow")

            call_kwargs = mock_client.chat.completions.create.call_args
            assert call_kwargs.kwargs["response_format"] == {"type": "json_object"}


# ── Tests: error handling / fallback ─────────────────────────────────────────

class TestOpenAIErrorHandling:

    def test_auth_error_falls_back(self, monkeypatch, caplog):
        """Invalid API key → logs error, returns fallback instruction."""
        import logging
        from openai import AuthenticationError as OAIAuthError
        monkeypatch.setattr(settings, "ai_api_key", "sk-bad-key")

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
            mock_client.chat.completions.create.side_effect = OAIAuthError(
                message="Invalid API key",
                response=mock_response,
                body={"error": {"message": "Invalid API key"}},
            )
            mock_get_client.return_value = mock_client

            with caplog.at_level(logging.ERROR, logger="backend.app.services.ai"):
                result = AIInterpreterService.interpret_request("Fetch data and notify via email")

        assert isinstance(result, WorkflowInstruction)
        assert result.workflow_name == "generic_automation"
        assert "authentication" in caplog.text.lower()

    def test_rate_limit_falls_back(self, monkeypatch):
        """Rate limit error → falls back without crashing."""
        from openai import RateLimitError as OAIRateLimitError
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.json.return_value = {}
            mock_client.chat.completions.create.side_effect = OAIRateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body={},
            )
            mock_get_client.return_value = mock_client

            result = AIInterpreterService.interpret_request("Generate a summary report")

        assert isinstance(result, WorkflowInstruction)

    def test_timeout_falls_back(self, monkeypatch):
        """Timeout → falls back without crashing."""
        from openai import APITimeoutError as OAITimeoutError
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = OAITimeoutError(request=MagicMock())
            mock_get_client.return_value = mock_client

            result = AIInterpreterService.interpret_request("Send weekly report to email")

        assert isinstance(result, WorkflowInstruction)

    def test_invalid_json_from_openai_falls_back(self, monkeypatch):
        """If OpenAI returns non-parseable JSON → falls back."""
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            bad_response = MagicMock()
            bad_response.choices[0].message.content = "This is not JSON at all!"
            bad_response.usage = None
            mock_client.chat.completions.create.return_value = bad_response
            mock_get_client.return_value = mock_client

            result = AIInterpreterService.interpret_request("Automate my data pipeline")

        assert isinstance(result, WorkflowInstruction)

    def test_schema_mismatch_from_openai_falls_back(self, monkeypatch):
        """If OpenAI returns valid JSON but wrong schema → falls back."""
        monkeypatch.setattr(settings, "ai_api_key", "sk-test-key")

        with patch("backend.app.services.ai._get_client") as mock_get_client:
            mock_client = MagicMock()
            bad_response = MagicMock()
            # Valid JSON but missing required fields
            bad_response.choices[0].message.content = json.dumps({"foo": "bar"})
            bad_response.usage = None
            mock_client.chat.completions.create.return_value = bad_response
            mock_get_client.return_value = mock_client

            result = AIInterpreterService.interpret_request("Run some automation")

        assert isinstance(result, WorkflowInstruction)

    def test_missing_api_key_uses_fallback(self, monkeypatch):
        """Empty API key → skips OpenAI entirely, returns fallback."""
        monkeypatch.setattr(settings, "ai_api_key", "")
        result = AIInterpreterService.interpret_request("Fetch data and update dashboard")
        assert result.workflow_name == "generic_automation"

    def test_placeholder_api_key_uses_fallback(self, monkeypatch):
        """'replace_me' placeholder → treated as not configured."""
        monkeypatch.setattr(settings, "ai_api_key", "replace_me")
        result = AIInterpreterService.interpret_request("Fetch data and update dashboard")
        assert result.workflow_name == "generic_automation"


# ── Tests: fallback quality ───────────────────────────────────────────────────

class TestFallbackInference:

    def test_email_keyword_adds_email_channel(self):
        result = AIInterpreterService._fallback_instruction("Send the report by email")
        assert "email" in result.channels

    def test_slack_keyword_adds_slack_channel(self):
        result = AIInterpreterService._fallback_instruction("Post results to Slack channel")
        assert "slack" in result.channels

    def test_report_keyword_adds_report_step(self):
        result = AIInterpreterService._fallback_instruction("Generate a weekly summary report")
        actions = [s.action for s in result.steps]
        assert "report_generation" in actions

    def test_transform_keyword_adds_transform_step(self):
        result = AIInterpreterService._fallback_instruction("Process and filter the raw data")
        actions = [s.action for s in result.steps]
        assert "transform_data" in actions

    def test_no_channel_defaults_to_dashboard(self):
        result = AIInterpreterService._fallback_instruction("Just run the automation")
        assert "dashboard" in result.channels

    def test_all_steps_have_valid_actions(self):
        result = AIInterpreterService._fallback_instruction(
            "Fetch data, generate report, send email, notify Slack"
        )
        valid_actions = {
            "api_fetch", "transform_data", "report_generation",
            "email_send", "slack_notify", "dashboard_update", "notification_send",
        }
        for step in result.steps:
            assert step.action in valid_actions
