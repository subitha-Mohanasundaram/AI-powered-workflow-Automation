"""
Request router — core automation submission endpoint.

Security headers documented in OpenAPI:
  X-API-Key        : Backend API access key (optional, required if API_ACCESS_KEY is set)
  X-Idempotency-Key: Client-generated key; repeated calls with same key return the cached run
  X-Correlation-ID : Caller-supplied trace ID; auto-generated if absent
"""
import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..logging_config import correlation_id_var, get_logger
from ..models import IdempotencyRecord, WorkflowRun
from ..security import require_api_key
from ..schemas import UserRequestCreate, WorkflowRunResponse
from ..services.ai import AIInterpreterService
from ..services.delivery import ResultDeliveryService
from ..services.execution import ExecutionEngineService
from ..services.workflow_generator import WorkflowGeneratorService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["requests"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/requests",
    response_model=WorkflowRunResponse,
    summary="Submit an automation request",
    description=(
        "Accepts a plain-language automation description, interprets it with the "
        "AI service, dispatches it to n8n, and delivers results via the requested "
        "channels (email, Slack, dashboard)."
    ),
    responses={
        200: {"description": "Run completed (or retrieved from idempotency cache)"},
        401: {"description": "Invalid or missing X-API-Key"},
        422: {"description": "Validation error in request body"},
        429: {"description": "Rate limit exceeded"},
    },
    openapi_extra={
        "security": [{"ApiKeyAuth": []}],
        "parameters": [
            {
                "name": "X-Idempotency-Key",
                "in": "header",
                "required": False,
                "schema": {"type": "string", "maxLength": 128},
                "description": (
                    "Unique client key for idempotent requests. "
                    "A repeated call with the same key returns the original run."
                ),
            },
            {
                "name": "X-Correlation-ID",
                "in": "header",
                "required": False,
                "schema": {"type": "string", "maxLength": 64},
                "description": "Caller trace ID for distributed tracing. Auto-generated if absent.",
            },
        ],
    },
)
def create_request(
    request_in: UserRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> WorkflowRun:
    idempotency_key = request.headers.get("X-Idempotency-Key", "").strip()
    correlation_id = request.headers.get("X-Correlation-ID", "").strip() or str(uuid.uuid4())

    # Inject correlation ID into log context for this request.
    token = correlation_id_var.set(correlation_id)

    try:
        # ── Idempotency check ────────────────────────────────────────────────
        if idempotency_key:
            existing_key = (
                db.query(IdempotencyRecord)
                .filter(IdempotencyRecord.key == idempotency_key)
                .first()
            )
            if existing_key:
                existing_run = db.query(WorkflowRun).filter(WorkflowRun.id == existing_key.run_id).first()
                if existing_run:
                    logger.info(
                        "Idempotency hit | key=%s | run_id=%s",
                        idempotency_key,
                        existing_run.id,
                    )
                    return existing_run

        logger.info(
            "Processing automation request | user_id=%s | cid=%s",
            request_in.user_id,
            correlation_id,
        )

        # ── AI interpretation ────────────────────────────────────────────────
        # Check clarification first
        clarification = AIInterpreterService.check_clarification(request_in.request_text)
        if clarification.needs_clarification:
            return {
                "status": "needs_clarification",
                "question": clarification.question,
                "run_id": None,
            }

        instruction = AIInterpreterService.interpret_request(request_in.request_text)

        # ── Persist initial run record ───────────────────────────────────────
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
        logger.info("Run record created | run_id=%d", run.id)

        # ── Generate payload ─────────────────────────────────────────────────
        payload = WorkflowGeneratorService.generate_payload(
            instruction=instruction,
            run_id=run.id,
            raw_request=request_in.request_text,
            correlation_id=correlation_id,
        )
        run.workflow_payload = json.dumps(payload)

        # ── Execute via n8n ──────────────────────────────────────────────────
        execution_result = ExecutionEngineService.execute(payload, db=db)
        run.execution_status = execution_result.status
        run.execution_output = json.dumps(execution_result.output)
        logger.info(
            "Execution complete | run_id=%d | status=%s",
            run.id,
            execution_result.status,
        )

        # ── Deliver results ──────────────────────────────────────────────────
        delivery_result = ResultDeliveryService.deliver(
            user_id=request_in.user_id,
            channels=instruction.channels,
            execution_output=execution_result.output,
        )
        if delivery_result and all(s in {"sent", "stored"} for s in delivery_result.values()):
            run.delivery_status = "success"
        elif any(s == "failed" for s in delivery_result.values()):
            run.delivery_status = "partial_or_failed"
        else:
            run.delivery_status = "pending_or_skipped"

        logger.info(
            "Delivery complete | run_id=%d | delivery_status=%s | channels=%s",
            run.id,
            run.delivery_status,
            delivery_result,
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        # ── Record idempotency key ───────────────────────────────────────────
        if idempotency_key:
            try:
                record = IdempotencyRecord(
                    key=idempotency_key[:128],
                    user_id=request_in.user_id,
                    run_id=run.id,
                    correlation_id=correlation_id,
                )
                db.add(record)
                db.commit()
            except Exception as exc:
                # Non-fatal: log and continue; the run itself succeeded.
                logger.warning("Failed to persist idempotency record | error=%s", exc)
                db.rollback()

        return run

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unhandled error in create_request | error=%s", exc, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error processing automation request")
    finally:
        correlation_id_var.reset(token)


@router.post(
    "/webhook/intake",
    response_model=WorkflowRunResponse,
    summary="Webhook intake (alias for /requests)",
    description="External webhook endpoint — identical behaviour to POST /api/requests.",
    openapi_extra={"security": [{"ApiKeyAuth": []}]},
)
def intake_webhook(
    request_in: UserRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> WorkflowRun:
    return create_request(request_in, request, db)


@router.get(
    "/runs",
    response_model=list[WorkflowRunResponse],
    summary="List recent workflow runs",
    openapi_extra={"security": [{"ApiKeyAuth": []}]},
)
def list_runs(
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[WorkflowRun]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    return db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(limit).all()


@router.get(
    "/runs/{run_id}",
    response_model=WorkflowRunResponse,
    summary="Get a single workflow run",
    openapi_extra={"security": [{"ApiKeyAuth": []}]},
)
def get_run(run_id: int, db: Session = Depends(get_db)) -> WorkflowRun:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
