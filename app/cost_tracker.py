from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ApiCallLog


def log_call(
    db: Session,
    *,
    provider: str,
    task_type: str,
    related_type: str,
    related_id: int,
    units: int,
    cost_usd: float,
) -> ApiCallLog:
    """Every vision/embedding call gets one row here, no exceptions --
    requirement #7 ('cost tracked, if AI is used ... per call, attributed'),
    even though the free tier means cost_usd is usually 0.0."""
    row = ApiCallLog(
        provider=provider,
        task_type=task_type,
        related_type=related_type,
        related_id=related_id,
        units=units,
        cost_usd=cost_usd,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
