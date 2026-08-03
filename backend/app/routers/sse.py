"""
Server-Sent Events router — real-time workflow run status streaming.
"""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..logging_config import get_logger
from ..models import WorkflowRun
from ..models_v2 import ExecutionLog

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sse"])

_TERMINAL_STATUSES = {"success", "failed", "cancelled"}
_POLL_INTERVAL = 1.0  # seconds between DB polls


async def _run_event_generator(run_id: int) -> AsyncGenerator[str, None]:
    """
    Poll the DB every second and emit SSE events for the run's status.
    Closes the stream when status reaches a terminal state.
    """
    last_step_count = 0

    while True:
        db: Session = SessionLocal()
        try:
            run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if not run:
                error_event = json.dumps({"error": "Run not found", "run_id": run_id})
                yield f"event: error\ndata: {error_event}\n\n"
                return

            # Fetch step logs
            logs = (
                db.query(ExecutionLog)
                .filter(ExecutionLog.run_id == run_id)
                .order_by(ExecutionLog.step_index)
                .all()
            )
            steps = [
                {
                    "step_index": log.step_index,
                    "step_name": log.step_name,
                    "action": log.action,
                    "status": log.status,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                    "duration_ms": log.duration_ms,
                    "retry_count": log.retry_count,
                    "error_message": log.error_message,
                }
                for log in logs
            ]

            event_data = json.dumps({
                "run_id": run_id,
                "status": run.execution_status,
                "steps": steps,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            })
            yield f"data: {event_data}\n\n"

            # Close stream on terminal status
            if run.execution_status in _TERMINAL_STATUSES:
                yield "event: done\ndata: {}\n\n"
                return

        except Exception as exc:
            logger.error("SSE polling error | run_id=%d | error=%s", run_id, exc)
            error_event = json.dumps({"error": str(exc), "run_id": run_id})
            yield f"event: error\ndata: {error_event}\n\n"
            return
        finally:
            db.close()

        await asyncio.sleep(_POLL_INTERVAL)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int):
    """
    Stream real-time SSE updates for a workflow run.
    Polls the DB every second and closes when the run reaches a terminal status.
    No auth required for streaming (uses run_id as implicit access token).
    """
    # Quick existence check before opening SSE stream
    db: Session = SessionLocal()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
    finally:
        db.close()

    return StreamingResponse(
        _run_event_generator(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
