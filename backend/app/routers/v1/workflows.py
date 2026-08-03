"""
Workflow CRUD router (v1).
Prefix: /api/v1/workflows
"""
import json
import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...logging_config import get_logger
from ...models import WorkflowRun
from ...models_v2 import User, Workflow, WorkflowVersion
from ...services.ai import AIInterpreterService
from ...services.auth import get_current_user
from ...services.execution import ExecutionEngineService
from ...services.workflow_generator import WorkflowGeneratorService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows-v1"])


# ── Request / Response schemas ────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    natural_language_request: str = Field(..., min_length=10, max_length=2000)
    name: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=2000)
    tags: Optional[list[str]] = None
    category: Optional[str] = Field(None, max_length=128)


class WorkflowUpdate(BaseModel):
    natural_language_request: Optional[str] = Field(None, min_length=10, max_length=2000)
    name: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=2000)
    tags: Optional[list[str]] = None
    category: Optional[str] = Field(None, max_length=128)


class WorkflowVersionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    version_number: int
    definition_json: str
    change_summary: str
    is_current: bool
    created_at: datetime


class WorkflowResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    user_id: int
    name: str
    description: str
    natural_language_request: str
    current_version_id: Optional[int]
    is_active: bool
    is_public: bool
    tags: str
    category: str
    total_runs: int
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_workflow_or_404(workflow_id: int, user: User, db: Session) -> Workflow:
    wf = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.user_id == user.id,
        Workflow.is_active == True,
    ).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


def _next_version_number(workflow_id: int, db: Session) -> int:
    from sqlalchemy import func
    max_ver = db.query(func.max(WorkflowVersion.version_number)).filter(
        WorkflowVersion.workflow_id == workflow_id
    ).scalar()
    return (max_ver or 0) + 1


def _create_version(workflow: Workflow, instruction, db: Session, change_summary: str = "Initial version") -> WorkflowVersion:
    """Create a new WorkflowVersion and set it as current."""
    # Mark all existing versions as not current
    db.query(WorkflowVersion).filter(
        WorkflowVersion.workflow_id == workflow.id
    ).update({"is_current": False})

    ver_num = _next_version_number(workflow.id, db)
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=ver_num,
        definition_json=instruction.model_dump_json(),
        change_summary=change_summary,
        created_by=workflow.user_id,
        is_current=True,
    )
    db.add(version)
    db.flush()

    workflow.current_version_id = version.id
    workflow.updated_at = datetime.now(UTC)
    return version


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=WorkflowResponse, status_code=201)
def create_workflow(
    body: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new workflow from a natural language request."""
    instruction = AIInterpreterService.interpret_request(body.natural_language_request)

    workflow_name = body.name or instruction.workflow_name.replace("_", " ").title()
    tags_json = json.dumps(body.tags or [])

    wf = Workflow(
        user_id=current_user.id,
        name=workflow_name,
        description=body.description or "",
        natural_language_request=body.natural_language_request,
        is_active=True,
        tags=tags_json,
        category=body.category or "",
    )
    db.add(wf)
    db.flush()

    _create_version(wf, instruction, db, change_summary="Initial version")
    db.commit()
    db.refresh(wf)
    logger.info("Workflow created | workflow_id=%d | user_id=%d", wf.id, current_user.id)
    return wf


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's workflows with optional active filter and pagination."""
    query = db.query(Workflow).filter(Workflow.user_id == current_user.id)
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    offset = (page - 1) * page_size
    return query.order_by(Workflow.created_at.desc()).offset(offset).limit(page_size).all()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single workflow with its current version info."""
    return _get_workflow_or_404(workflow_id, current_user, db)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: int,
    body: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a workflow. If NL request changes, creates a new version."""
    wf = _get_workflow_or_404(workflow_id, current_user, db)

    version_needed = False
    if body.natural_language_request and body.natural_language_request != wf.natural_language_request:
        wf.natural_language_request = body.natural_language_request
        version_needed = True

    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.tags is not None:
        wf.tags = json.dumps(body.tags)
    if body.category is not None:
        wf.category = body.category

    if version_needed:
        instruction = AIInterpreterService.interpret_request(wf.natural_language_request)
        _create_version(wf, instruction, db, change_summary="Updated via PUT")

    db.commit()
    db.refresh(wf)
    return wf


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a workflow (sets is_active=False)."""
    wf = _get_workflow_or_404(workflow_id, current_user, db)
    wf.is_active = False
    wf.updated_at = datetime.now(UTC)
    db.commit()
    return None


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionResponse])
def list_versions(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of a workflow."""
    _get_workflow_or_404(workflow_id, current_user, db)
    versions = (
        db.query(WorkflowVersion)
        .filter(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
        .all()
    )
    return versions


@router.post("/{workflow_id}/run")
def run_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute the workflow immediately. Returns the WorkflowRun record."""
    wf = _get_workflow_or_404(workflow_id, current_user, db)

    correlation_id = str(uuid.uuid4())
    instruction = AIInterpreterService.interpret_request(wf.natural_language_request)

    run = WorkflowRun(
        user_id=str(current_user.id),
        request_text=wf.natural_language_request,
        interpreted_instructions=instruction.model_dump_json(),
        workflow_payload="{}",
        execution_status="pending",
        delivery_status="pending",
        execution_output="{}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    payload = WorkflowGeneratorService.generate_payload(
        instruction=instruction,
        run_id=run.id,
        raw_request=wf.natural_language_request,
        correlation_id=correlation_id,
    )
    run.workflow_payload = json.dumps(payload)

    result = ExecutionEngineService.execute(payload, db=db, user_id=current_user.id)
    run.execution_status = result.status
    run.execution_output = json.dumps(result.output)

    # Update workflow stats
    wf.total_runs += 1
    wf.last_run_at = datetime.now(UTC)
    wf.last_run_status = result.status

    db.commit()
    db.refresh(run)

    return {
        "run_id": run.id,
        "workflow_id": wf.id,
        "status": run.execution_status,
        "correlation_id": correlation_id,
        "created_at": run.created_at.isoformat(),
    }
