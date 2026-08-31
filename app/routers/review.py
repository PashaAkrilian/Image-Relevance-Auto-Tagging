from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReviewDecision, ReviewDecisionValue, Suggestion, SuggestionStatus
from app.schemas import ReviewDecisionIn, ReviewDecisionOut, SuggestionOut

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/pending", response_model=list[SuggestionOut])
def list_pending_reviews(db: Session = Depends(get_db)):
    """Accepted suggestions -- i.e. things the guard is proposing to a
    human -- that don't have a review decision yet."""
    return (
        db.query(Suggestion)
        .outerjoin(ReviewDecision)
        .filter(Suggestion.status == SuggestionStatus.ACCEPTED, ReviewDecision.id.is_(None))
        .order_by(Suggestion.post_id, Suggestion.rank)
        .all()
    )


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def inspect_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """Inspect *why* an image was selected or refused for a post -- the
    `reason` field is always populated, accepted or not."""
    suggestion = db.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="suggestion not found")
    return suggestion


@router.post("/suggestions/{suggestion_id}/decision", response_model=ReviewDecisionOut)
def decide_suggestion(suggestion_id: int, payload: ReviewDecisionIn, db: Session = Depends(get_db)):
    suggestion = db.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="suggestion not found")

    existing = db.query(ReviewDecision).filter(ReviewDecision.suggestion_id == suggestion_id).first()
    if existing is not None:
        existing.decision = ReviewDecisionValue(payload.decision)
        existing.note = payload.note
        db.commit()
        db.refresh(existing)
        return existing

    decision = ReviewDecision(
        suggestion_id=suggestion_id,
        decision=ReviewDecisionValue(payload.decision),
        note=payload.note,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision
