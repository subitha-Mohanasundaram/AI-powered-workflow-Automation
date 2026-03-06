import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IdempotencyRecord, WorkflowRun
from ..security import require_api_key
from ..schemas import UserRequestCreate, WorkflowRunResponse
from ..services.ai import AIInterpreterService
from ..services.delivery import ResultDeliveryService
from ..services.execution import ExecutionEngineService
from ..services.workflow_generator import WorkflowGeneratorService

router = APIRouter(prefix="/api", tags=["requests"], dependencies=[Depends(require_api_key)])


@router.post("/requests", response_model=WorkflowRunResponse)
def create_request(request_in: UserRequestCreate, request: Request, db: Session = Depends(get_db)):
    idempotency_key = request.headers.get("X-Idempotency-Key", "").strip()
    if idempotency_key:
        existing_key = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == idempotency_key).first()
        if existing_key:
            existing_run = db.query(WorkflowRun).filter(WorkflowRun.id == existing_key.run_id).first()
            if existing_run:
                return existing_run

    correlation_id = request.headers.get("X-Correlation-ID", "").strip() or str(uuid.uuid4())
    instruction = AIInterpreterService.interpret_request(request_in.request_text)

    run = WorkflowRun(
        user_id=request_in.user_id,
        request_text=request_in.request_text,
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
        raw_request=request_in.request_text,
        correlation_id=correlation_id,
    )
    run.workflow_payload = json.dumps(payload)

    execution_result = ExecutionEngineService.execute(payload)
    run.execution_status = execution_result.status
    run.execution_output = json.dumps(execution_result.output)

    delivery_result = ResultDeliveryService.deliver(
        user_id=request_in.user_id,
        channels=instruction.channels,
        execution_output=execution_result.output,
    )
    if delivery_result and all(status in {"sent", "stored"} for status in delivery_result.values()):
        run.delivery_status = "success"
    elif any(status == "failed" for status in delivery_result.values()):
        run.delivery_status = "partial_or_failed"
    else:
        run.delivery_status = "pending_or_skipped"

    db.add(run)
    db.commit()
    db.refresh(run)

    if idempotency_key:
        record = IdempotencyRecord(
            key=idempotency_key[:128],
            user_id=request_in.user_id,
            run_id=run.id,
            correlation_id=correlation_id,
        )
        db.add(record)
        db.commit()

    return run


@router.post("/webhook/intake", response_model=WorkflowRunResponse)
def intake_webhook(request_in: UserRequestCreate, request: Request, db: Session = Depends(get_db)):
    return create_request(request_in, request, db)


@router.get("/runs", response_model=list[WorkflowRunResponse])
def list_runs(db: Session = Depends(get_db)):
    return db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(100).all()


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
