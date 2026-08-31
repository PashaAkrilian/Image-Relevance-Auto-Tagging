"""Generic background batch runner: slow/bulk vision & embedding work runs
here, off the request path, with retries, progress tracking, and a
BatchJob/BatchJobItem trail for the review API and eval script to inspect.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import SessionLocal
from app.models import BatchJob, BatchJobItem, JobStatus

logger = logging.getLogger("app.jobs")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_batch(
    *,
    job_type: str,
    item_type: str,
    item_ids: list[int],
    process_one: Callable[[Session, int], tuple[str, str | None]],
    settings: Settings,
) -> int:
    """process_one(db, item_id) -> ("succeeded" | "failed", error_message).

    Runs synchronously in the calling thread (invoked from FastAPI
    BackgroundTasks or a CLI script) so it never blocks a request while
    still being a real off-path job with its own progress row. Each item
    gets up to settings.batch_max_retries attempts with exponential backoff
    before being recorded as permanently failed.
    """
    db = SessionLocal()
    try:
        job = BatchJob(
            job_type=job_type,
            status=JobStatus.RUNNING,
            total_items=len(item_ids),
            started_at=_utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        for item_id in item_ids:
            item = BatchJobItem(batch_job_id=job.id, item_type=item_type, item_id=item_id)
            db.add(item)
            db.commit()
            db.refresh(item)

            status, error = "failed", "unknown error"
            for attempt in range(1, settings.batch_max_retries + 1):
                item.attempts = attempt
                try:
                    status, error = process_one(db, item_id)
                    break
                except Exception as exc:  # transient error from the provider/db -> retry
                    status, error = "failed", str(exc)
                    logger.warning("job=%s item=%s attempt=%s failed: %s", job_type, item_id, attempt, exc)
                    if attempt < settings.batch_max_retries:
                        time.sleep(settings.batch_retry_backoff_seconds * attempt)

            item.status = JobStatus.SUCCEEDED if status == "succeeded" else JobStatus.FAILED
            item.last_error = error
            db.commit()

            if status == "succeeded":
                job.completed_items += 1
            else:
                job.failed_items += 1
            db.commit()

        job.finished_at = _utcnow()
        job.status = JobStatus.FAILED if job.failed_items == job.total_items and job.total_items > 0 else (
            JobStatus.PARTIAL if job.failed_items > 0 else JobStatus.SUCCEEDED
        )
        db.commit()
        return job.id
    finally:
        db.close()
