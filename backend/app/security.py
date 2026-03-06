from fastapi import Header, HTTPException

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    # In local dev, auth is optional unless explicitly configured.
    if not settings.api_access_key:
        return
    if x_api_key != settings.api_access_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

