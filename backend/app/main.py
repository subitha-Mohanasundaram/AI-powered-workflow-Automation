from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .rate_limit import RateLimitMiddleware
from .routers.dashboard import router as dashboard_router
from .routers.health import router as health_router
from .routers.requests import router as request_router

app = FastAPI(title=settings.app_name)

allowed_origins = [origin.strip() for origin in settings.app_allowed_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.on_event("startup")
def on_startup():
    # Ensure model metadata is registered before table creation.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


app.include_router(health_router)
app.include_router(request_router)
app.include_router(dashboard_router)
