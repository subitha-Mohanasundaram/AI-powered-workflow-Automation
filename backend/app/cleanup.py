"""
Database retention / archival job.

Run this as a scheduled task (cron, APScheduler, k8s CronJob) to prevent
the workflow_runs table from growing unbounded.

Usage (one-shot via CLI):
    python -m backend.app.cleanup

Retention window is controlled by the RUN_RETENTION_DAYS env variable
(default 90 days).  Runs older than the retention window are deleted.
Idempotency records older than 7 days are always purged regardless of
the retention setting (they are only needed to deduplicate recent calls).
"""
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from .database import SessionLocal
from .logging_config import configure_logging, get_logger
from .models import IdempotencyRecord, WorkflowRun

configure_logging()
logger = get_logger(__name__)

# Idempotency keys are only useful for a short window.
IDEMPOTENCY_MAX_AGE_DAYS = 7


def run_cleanup(retention_days: int = 90, dry_run: bool = False) -> dict:
    """
    Delete old workflow runs and idempotency records.

    Args:
        retention_days: Delete WorkflowRun rows older than this many days.
        dry_run: If True, count rows that would be deleted but do not commit.

    Returns:
        Dict with keys 'runs_deleted' and 'idempotency_deleted'.
    """
    now = datetime.now(UTC)
    run_cutoff = now - timedelta(days=retention_days)
    idempotency_cutoff = now - timedelta(days=IDEMPOTENCY_MAX_AGE_DAYS)

    db = SessionLocal()
    try:
        # Count before deletion (used in dry-run mode and logging)
        runs_count = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.created_at < run_cutoff)
            .count()
        )
        idempotency_count = (
            db.query(IdempotencyRecord)
            .filter(IdempotencyRecord.created_at < idempotency_cutoff)
            .count()
        )

        logger.info(
            "Cleanup scan | run_cutoff=%s | runs_to_delete=%d | idempotency_to_delete=%d | dry_run=%s",
            run_cutoff.isoformat(),
            runs_count,
            idempotency_count,
            dry_run,
        )

        if not dry_run:
            db.execute(delete(WorkflowRun).where(WorkflowRun.created_at < run_cutoff))
            db.execute(
                delete(IdempotencyRecord).where(IdempotencyRecord.created_at < idempotency_cutoff)
            )
            db.commit()
            logger.info(
                "Cleanup complete | runs_deleted=%d | idempotency_deleted=%d",
                runs_count,
                idempotency_count,
            )

        return {"runs_deleted": runs_count, "idempotency_deleted": idempotency_count}

    except Exception as exc:
        logger.error("Cleanup failed | error=%s", exc, exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean up old workflow runs from the database.")
    parser.add_argument("--retention-days", type=int, default=90, help="Days to retain runs (default: 90)")
    parser.add_argument("--dry-run", action="store_true", help="Preview deletion without committing")
    args = parser.parse_args()

    result = run_cleanup(retention_days=args.retention_days, dry_run=args.dry_run)
    print(f"Cleanup result: {result}")
    sys.exit(0)
