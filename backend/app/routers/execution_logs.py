"""
Execution Logs router — per-step execution detail for workflow runs.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_v2 import ExecutionLog
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/v1", tags=["execution-logs"])


class ExecutionLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    run_id: int
    step_index: int
    step_name: str
    action: str
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    input_json: Optional[str]
    output_json: Optional[str]
    error_message: Optional[str]
    retry_count: int
    duration_ms: Optional[int]


@router.get("/runs/{run_id}/logs", response_model=list[ExecutionLogResponse])
def get_run_logs(
    run_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all ExecutionLog rows for a given run_id, ordered by step_index."""
    logs = (
        db.query(ExecutionLog)
        .filter(ExecutionLog.run_id == run_id)
        .order_by(ExecutionLog.step_index)
        .all()
    )
    return logs


@router.get("/runs/{run_id}/logs/{step_index}", response_model=ExecutionLogResponse)
def get_run_step_log(
    run_id: int,
    step_index: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a single step log by run_id and step_index."""
    log = (
        db.query(ExecutionLog)
        .filter(
            ExecutionLog.run_id == run_id,
            ExecutionLog.step_index == step_index,
        )
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Step log not found")
    return log


@router.get("/runs/{run_id}/failure-report")
def get_failure_report(
    run_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return the failure report for a run (if it failed).
    The report is stored in the WorkflowRun.execution_output JSON under 'failure_report'.
    """
    import json
    from ..models import WorkflowRun

    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        output = json.loads(run.execution_output or "{}")
    except (json.JSONDecodeError, ValueError):
        output = {}

    failure_report = output.get("failure_report")
    if not failure_report:
        if run.execution_status != "failed":
            raise HTTPException(status_code=404, detail="Run has not failed — no failure report available")
        raise HTTPException(status_code=404, detail="No failure report found for this run")

    return failure_report
