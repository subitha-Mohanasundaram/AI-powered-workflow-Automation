"""
Pytest configuration for the backend test suite.

Forces an in-memory SQLite database so tests never touch automation.db.
"""
import os

# Must be set before importing any app modules so Settings picks it up.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_automation.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_API_KEY", "")
os.environ.setdefault("API_ACCESS_KEY", "")
