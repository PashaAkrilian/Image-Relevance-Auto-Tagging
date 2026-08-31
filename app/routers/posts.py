from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.jobs.embedding_job import process_one_post_embedding
from app.jobs.matching_job import process_one_post_matching
from app.jobs.runner import run_batch
from app.models import Post, Suggestion, SuggestionStatus
from app.schemas import PostOut, PostSuggestionsResponse, SuggestionOut

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostOut])
def list_posts(db: Session = Depends(get_db)):
    return db.query(Post).order_by(Post.id).all()


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return post


@router.get("/{post_id}/images", response_model=PostSuggestionsResponse)
def get_post_suggestions(post_id: int, db: Session = Depends(get_db)):
    """The core read endpoint: ranked, guard-checked image suggestions for
    one post, plus the single best match (or None with an explanation)."""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.post_id == post_id)
        .order_by(
            Suggestion.status != SuggestionStatus.ACCEPTED,
            Suggestion.rank.is_(None),
            Suggestion.rank,
        )
        .all()
    )
    if not suggestions:
        raise HTTPException(
            status_code=404,
            detail="no suggestions computed yet for this post; run the matching batch first",
        )

    best = next((s for s in suggestions if s.status == SuggestionStatus.ACCEPTED and s.rank == 1), None)
    return PostSuggestionsResponse(post=post, suggestions=suggestions, best_match=best)


@router.post("/batch/embed")
def trigger_post_embedding_batch(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    post_ids = [row.id for row in db.query(Post.id).all()]
    if not post_ids:
        raise HTTPException(status_code=400, detail="no posts to embed; run the seed script first")

    def _run():
        run_batch(
            job_type="embedding",
            item_type="post",
            item_ids=post_ids,
            process_one=lambda db_, pid: process_one_post_embedding(db_, pid, settings),
            settings=settings,
        )

    background_tasks.add_task(_run)
    return {"status": "started", "queued_posts": len(post_ids)}


@router.post("/batch/match")
def trigger_matching_batch(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Rank + guard-check every post against the image corpus and persist
    Suggestion rows (this is what powers GET /posts/:id/images)."""
    post_ids = [row.id for row in db.query(Post.id).filter(Post.embedding.isnot(None)).all()]
    if not post_ids:
        raise HTTPException(status_code=400, detail="no embedded posts to match; run post embedding first")

    def _run():
        run_batch(
            job_type="matching",
            item_type="post",
            item_ids=post_ids,
            process_one=lambda db_, pid: process_one_post_matching(db_, pid, settings),
            settings=settings,
        )

    background_tasks.add_task(_run)
    return {"status": "started", "queued_posts": len(post_ids)}
