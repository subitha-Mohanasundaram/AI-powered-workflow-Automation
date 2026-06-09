"""
Application settings loaded from environment variables / .env file.
Secrets are never printed; validators enforce required values at startup.
"""
import secrets
import sys
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────────
    app_name: str = "AI Workflow Automation"
    app_env: str = "development"
    app_port: int = 8000
    app_allowed_origins: str = "*"
    log_level: str = "INFO"

    # ── Encryption ────────────────────────────────────────────────
    secret_key: str = ""   # Used to encrypt confidential user data at rest

    # ── Database ───────────────────────────────────────────────────
    # Set DATABASE_URL to a PostgreSQL DSN in production.
    # Example: postgresql+psycopg2://user:pass@host:5432/dbname
    database_url: str = "sqlite:///./automation.db"

    # ── API Security ───────────────────────────────────────────────
    api_access_key: str = ""
    dashboard_token: str = ""           # Token for /dashboard access
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # ── AI / LLM ──────────────────────────────────────────────────
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: int = 30

    # ── n8n ────────────────────────────────────────────────────────
    n8n_base_url: str = "http://localhost:5678"
    n8n_execution_webhook_path: str = "/webhook/execute-workflow"
    n8n_timeout_seconds: int = 45
    n8n_retry_attempts: int = 3
    n8n_retry_backoff_seconds: float = 1.0
    n8n_webhook_url: str = ""

    # ── SMTP ───────────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@example.com"

    # ── Slack ──────────────────────────────────────────────────────
    slack_webhook_url: str = ""

    # ── Database archival ─────────────────────────────────────────
    run_retention_days: int = 90        # Runs older than this are archived/deleted

    # ── Validators ────────────────────────────────────────────────

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v.lower()

    @field_validator("database_url")
    @classmethod
    def warn_sqlite_production(cls, v: str) -> str:
        # Validation runs before model_validator so we just return; the
        # model_validator checks the combination of env + db.
        return v

    @model_validator(mode="after")
    def check_production_requirements(self) -> "Settings":
        if self.app_env == "production":
            if self.database_url.startswith("sqlite"):
                print(
                    "[WARN] SQLite is not recommended in production. "
                    "Set DATABASE_URL to a PostgreSQL/MySQL DSN.",
                    file=sys.stderr,
                )
            if not self.ai_api_key:
                print(
                    "[WARN] AI_API_KEY is not set. "
                    "The system will use rule-based fallback instead of LLM interpretation.",
                    file=sys.stderr,
                )
        return self

    def verify_api_key(self, provided: Optional[str]) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        if not self.api_access_key:
            return True          # auth not required
        if not provided:
            return False
        return secrets.compare_digest(self.api_access_key, provided)

    def verify_dashboard_token(self, provided: Optional[str]) -> bool:
        """Constant-time comparison for dashboard token."""
        if not self.dashboard_token:
            return True          # dashboard auth not required when token not configured
        if not provided:
            return False
        return secrets.compare_digest(self.dashboard_token, provided)


settings = Settings()
