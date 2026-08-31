from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiCallLog
from app.schemas import CostSummaryResponse, CostSummaryRow

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/summary", response_model=CostSummaryResponse)
def cost_summary(db: Session = Depends(get_db)):
    rows = (
        db.query(
            ApiCallLog.provider,
            ApiCallLog.task_type,
            func.count(ApiCallLog.id),
            func.coalesce(func.sum(ApiCallLog.units), 0),
            func.coalesce(func.sum(ApiCallLog.cost_usd), 0.0),
        )
        .group_by(ApiCallLog.provider, ApiCallLog.task_type)
        .all()
    )
    summary_rows = [
        CostSummaryRow(provider=p, task_type=t, calls=c, total_units=int(u), total_cost_usd=float(cost))
        for p, t, c, u, cost in rows
    ]
    return CostSummaryResponse(
        rows=summary_rows,
        total_cost_usd=sum(r.total_cost_usd for r in summary_rows),
        total_calls=sum(r.calls for r in summary_rows),
    )
