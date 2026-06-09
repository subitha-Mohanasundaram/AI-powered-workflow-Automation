"""
Health check router.

GET /health — lightweight liveness probe used by Docker, k8s, and load balancers.
GET /health/ready — readiness probe that verifies the database is reachable.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 OK if the application process is running.",
)
def health_check() -> dict:
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Returns 200 OK if the application can reach the database.",
    responses={
        200: {"description": "Application is ready"},
        503: {"description": "Database is unreachable"},
    },
)
def readiness_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database unavailable")
