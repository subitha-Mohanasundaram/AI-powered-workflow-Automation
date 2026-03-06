from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "AI Workflow Automation"
    app_env: str = "development"
    app_port: int = 8000
    app_allowed_origins: str = "*"

    database_url: str = "sqlite:///./automation.db"

    api_access_key: str = ""
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: int = 30

    n8n_base_url: str = "http://localhost:5678"
    n8n_execution_webhook_path: str = "/webhook/execute-workflow"
    n8n_timeout_seconds: int = 45
    n8n_retry_attempts: int = 3
    n8n_retry_backoff_seconds: float = 1.0

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = "user"
    smtp_password: str = "password"
    email_from: str = "no-reply@example.com"

    slack_webhook_url: str = ""


settings = Settings()
