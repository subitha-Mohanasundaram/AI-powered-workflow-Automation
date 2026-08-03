"""
API key and JWT authentication dependencies.
Uses constant-time comparison (secrets.compare_digest) to prevent timing attacks.
"""
from typing import Optional

from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency that enforces API key authentication.

    - If API_ACCESS_KEY is not configured, the endpoint is publicly accessible.
    - Comparison is performed in constant time to prevent timing-based attacks.
    """
    if not settings.verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Optional auth dependency — accepts either:
      - Bearer JWT token (Authorization: Bearer <token>)
      - X-API-Key header

    Returns the authenticated User if JWT is provided and valid,
    None if only API key is used (legacy mode), or raises 401 if
    credentials are present but invalid.
    """
    from .services.auth import decode_token

    # Try Bearer JWT first
    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") == "access":
                from .models_v2 import User
                user_id = payload.get("sub")
                if user_id:
                    user = db.query(User).filter(User.id == int(user_id)).first()
                    if user and user.is_active:
                        return user
        except HTTPException:
            pass  # fall through to API key check

    # Try X-API-Key
    if x_api_key and settings.verify_api_key(x_api_key):
        return None  # API key authenticated but no user object

    # If API key not required and no JWT, allow through
    if not settings.api_access_key:
        return None

    raise HTTPException(status_code=401, detail="Authentication required")
