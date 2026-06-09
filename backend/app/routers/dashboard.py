"""
Dashboard router.

Serves the HTML dashboard at /dashboard.

Authentication:
  When DASHBOARD_TOKEN is set in the environment, accessing /dashboard
  requires the correct token via the `token` query parameter or the
  `X-Dashboard-Token` header.  Without it the dashboard is open (useful
  in local development / demo mode).
"""
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..logging_config import get_logger
from ..models import WorkflowRun

logger = get_logger(__name__)
router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="backend/app/templates")


def _require_dashboard_auth(
    token: str | None = Query(default=None, alias="token"),
    x_dashboard_token: str | None = Header(default=None),
) -> None:
    """
    Dependency: enforces dashboard token when DASHBOARD_TOKEN is configured.
    Accepts the token from either the `?token=` query param or X-Dashboard-Token header.
    """
    provided = token or x_dashboard_token
    if not settings.verify_dashboard_token(provided):
        raise HTTPException(
            status_code=401,
            detail="Dashboard access requires a valid token. "
                   "Pass ?token=<DASHBOARD_TOKEN> or X-Dashboard-Token header.",
        )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get(
    "/dashboard",
    response_class=HTMLResponse,
    summary="Workflow automation dashboard",
    description=(
        "Renders the HTML dashboard showing recent workflow runs. "
        "When DASHBOARD_TOKEN is configured, a token must be supplied via "
        "the `?token=` query parameter or `X-Dashboard-Token` header."
    ),
    dependencies=[Depends(_require_dashboard_auth)],
)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    runs = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50).all()
    items = []
    for run in runs:
        output: dict = {}
        payload: dict = {}
        instructions: dict = {}
        try:
            output = json.loads(run.execution_output or "{}")
        except (json.JSONDecodeError, TypeError):
            output = {"raw": run.execution_output}
        try:
            payload = json.loads(run.workflow_payload or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {"raw": run.workflow_payload}
        try:
            instructions = json.loads(run.interpreted_instructions or "{}")
        except (json.JSONDecodeError, TypeError):
            instructions = {"raw": run.interpreted_instructions}

        items.append(
            {
                "id": run.id,
                "user_id": run.user_id,
                "request_text": run.request_text,
                "execution_status": run.execution_status,
                "delivery_status": run.delivery_status,
                "output": output,
                "payload": payload,
                "instructions": instructions,
                "created_at": run.created_at.isoformat(),
            }
        )

    auth_enabled = bool(settings.dashboard_token)
    logger.debug("Dashboard rendered | runs=%d | auth_enabled=%s", len(items), auth_enabled)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "runs": items, "auth_enabled": auth_enabled},
    )
