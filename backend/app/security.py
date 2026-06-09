"""
API key authentication dependency.
Uses constant-time comparison (secrets.compare_digest) to prevent timing attacks.
"""
from fastapi import Header, HTTPException

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency that enforces API key authentication.

    - If API_ACCESS_KEY is not configured, the endpoint is publicly accessible.
    - Comparison is performed in constant time to prevent timing-based attacks.
    """
    if not settings.verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
