"""
Authentication router — register, login, token refresh, logout, and profile.
Prefix: /api/v1/auth
"""
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..logging_config import get_logger
from ..models_v2 import RefreshToken, User
from ..services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    hash_token,
    verify_password,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Request / Response schemas ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=256)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=256)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    email_verified: bool
    last_login_at: datetime | None
    created_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _issue_tokens(user: User, db: Session, device_info: str = "") -> TokenResponse:
    """Create and persist a new access+refresh token pair for a user."""
    access = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    refresh = create_refresh_token({"sub": str(user.id)})

    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=expire,
        device_info=device_info[:512] if device_info else "",
    )
    db.add(rt)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new user account and return tokens."""
    email = body.email.lower().strip()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "message": "Email already registered"},
        )

    user = User(
        email=email,
        password_hash_bcrypt=hash_password(body.password),
        role="user",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registered | user_id=%d | email=%s", user.id, email)

    device_info = request.headers.get("User-Agent", "")
    return _issue_tokens(user, db, device_info)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Login with email and password. Enforces lockout after 5 failed attempts in 15 min."""
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # Generic error to avoid user enumeration
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthorized", "message": "Invalid email or password"},
    )

    if not user:
        raise _invalid

    # Check account lockout
    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "locked",
                "message": f"Account locked. Try again in {remaining} seconds.",
            },
        )

    # Verify password
    if not verify_password(body.password, user.password_hash_bcrypt):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            logger.warning("Account locked after 5 failures | user_id=%d", user.id)
        db.commit()
        raise _invalid

    # Successful login — reset counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()

    logger.info("User logged in | user_id=%d", user.id)
    device_info = request.headers.get("User-Agent", "")
    return _issue_tokens(user, db, device_info)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """Validate refresh token from DB and return a new access token."""
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    token_hash = hash_token(body.refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not rt:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    if rt.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    if rt.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate: revoke old token, issue new pair
    rt.revoked_at = datetime.now(UTC)
    db.commit()

    new_access = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=expire,
        device_info=rt.device_info or "",
    )
    db.add(new_rt)
    db.commit()
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke the supplied refresh token (logout from current device)."""
    token_hash = hash_token(body.refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if rt and rt.revoked_at is None:
        rt.revoked_at = datetime.now(UTC)
        db.commit()
    return None


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        email_verified=current_user.email_verified,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
    )
