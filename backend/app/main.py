"""
FastAPI application entry point.

Initialises:
  - Structured logging
  - CORS middleware
  - Per-user rate limiting middleware
  - Database table creation on startup
  - OpenAPI security scheme documentation
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from .config import settings
from .database import Base, engine
from .logging_config import configure_logging, get_logger
from .rate_limit import RateLimitMiddleware
from .routers.ai import router as ai_router
from .routers.auth import router as auth_router
from .routers.dashboard import router as dashboard_router
from .routers.execution_logs import router as execution_logs_router
from .routers.health import router as health_router
from .routers.leetcode import router as leetcode_router
from .routers.plugins import router as plugins_router
from .routers.requests import router as request_router
from .routers.scheduled import router as scheduled_router
from .routers.sse import router as sse_router
from .routers.v1.workflows import router as workflows_v1_router

# Configure logging before anything else so all startup messages are captured.
configure_logging(settings.log_level)
logger = get_logger(__name__)


def _custom_openapi(app: FastAPI):
    """Attach OpenAPI security schemes and global metadata once."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "AI-powered workflow automation API. "
            "Accepts natural-language automation requests, interprets them with an LLM, "
            "and dispatches structured workflows to n8n for execution."
        ),
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": (
                "API access key.  Required when API_ACCESS_KEY is configured. "
                "Pass the key in the X-API-Key request header."
            ),
        }
    }
    schema["info"]["x-custom-headers"] = {
        "X-API-Key": "API access key (required if API_ACCESS_KEY is configured)",
        "X-Idempotency-Key": "Client-generated key for idempotent requests",
        "X-Correlation-ID": "Distributed tracing ID (auto-generated if absent)",
    }
    app.openapi_schema = schema
    return schema


# ── Lifespan (replaces deprecated @app.on_event) ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from . import models  # noqa: F401
    from . import models_v2  # noqa: F401  — Phase 2 tables
    from .services.scheduler import reload_all_jobs, start_scheduler, stop_scheduler

    logger.info("Starting %s | env=%s | db=%s", settings.app_name, settings.app_env, settings.database_url.split("://")[0])
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created")

    if not settings.ai_api_key:
        logger.warning("AI_API_KEY is not set — LLM interpretation disabled, rule-based fallback active")

    # Start the background scheduler
    start_scheduler()
    loaded = reload_all_jobs()
    logger.info("Scheduler ready | active_jobs=%d", loaded)

    yield  # application runs here

    stop_scheduler()
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = [o.strip() for o in settings.app_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(ai_router)
app.include_router(leetcode_router)
app.include_router(scheduled_router)
app.include_router(request_router)
app.include_router(dashboard_router)

# ── Phase 1 + 2 v1 routers ────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(execution_logs_router)
app.include_router(plugins_router)
app.include_router(sse_router)
app.include_router(workflows_v1_router)

# ── OpenAPI schema customisation ──────────────────────────────────────────────
app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]
