from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.guard import ImageCandidate, run_guard
from app.matching import rank_images
from app.models import Image, Post, Suggestion, SuggestionStatus, TagStatus


def process_one_post_matching(db: Session, post_id: int, settings: Settings | None = None) -> tuple[str, str | None]:
    """Rank every embedded, trustworthy image against one post, run the
    mismatch guard over the full candidate set, and persist the result as
    Suggestion rows -- accepted candidates ranked first, then every
    rejected candidate with its reason, so the review API can show exactly
    why an image was or wasn't chosen."""
    settings = settings or get_settings()
    post = db.get(Post, post_id)
    if post is None:
        return "failed", f"post {post_id} not found"
    if post.embedding is None:
        return "failed", f"post {post_id} has no embedding yet"

    images = (
        db.query(Image)
        .filter(Image.tag_status != TagStatus.INVALID, Image.embedding.isnot(None))
        .all()
    )

    ranked = rank_images(post.embedding, [(img.id, img.embedding) for img in images])
    by_id = {img.id: img for img in images}
    candidates = [
        ImageCandidate(
            image_id=image_id,
            tag_status=by_id[image_id].tag_status.value,
            subject=by_id[image_id].subject,
            tag_category=by_id[image_id].tag_category,
            similarity=similarity,
        )
        for image_id, similarity in ranked
    ]

    decisions = run_guard(post.title, post.body, candidates, settings.similarity_threshold)

    db.query(Suggestion).filter(Suggestion.post_id == post.id).delete()
    db.commit()

    for d in decisions:
        db.add(
            Suggestion(
                post_id=post.id,
                image_id=d.image_id,
                similarity_score=d.similarity,
                rank=d.rank,
                status=SuggestionStatus(d.status),
                reason=d.reason,
            )
        )
    db.commit()
    return "succeeded", None
