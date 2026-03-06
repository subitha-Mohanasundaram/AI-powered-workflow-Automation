import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import WorkflowRun

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="backend/app/templates")


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    runs = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50).all()
    items = []
    for run in runs:
        output = {}
        try:
            output = json.loads(run.execution_output or "{}")
        except Exception:
            output = {"raw": run.execution_output}
        items.append(
            {
                "id": run.id,
                "user_id": run.user_id,
                "request_text": run.request_text,
                "execution_status": run.execution_status,
                "delivery_status": run.delivery_status,
                "output": output,
                "created_at": run.created_at.isoformat(),
            }
        )
    return templates.TemplateResponse("dashboard.html", {"request": request, "runs": items})

