from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.cost_tracker import log_call
from app.embeddings.factory import get_embedding_provider
from app.models import Image, Post, TagStatus


def process_one_image_embedding(db: Session, image_id: int, settings: Settings | None = None) -> tuple[str, str | None]:
    settings = settings or get_settings()
    image = db.get(Image, image_id)
    if image is None:
        return "failed", f"image {image_id} not found"
    if image.tag_status == TagStatus.INVALID:
        # Never trust invalid vision output -> never embed it either.
        return "succeeded", "skipped: tag_status=invalid"

    provider = get_embedding_provider(settings)
    text = f"{image.caption or ''}. Subject: {image.subject or ''}. Attributes: {', '.join(image.attributes or [])}"
    result = provider.embed(text)
    image.embedding = result.vector
    db.commit()
    log_call(
        db,
        provider=provider.name,
        task_type="embedding",
        related_type="image",
        related_id=image.id,
        units=result.units,
        cost_usd=result.cost_usd,
    )
    return "succeeded", None


def process_one_post_embedding(db: Session, post_id: int, settings: Settings | None = None) -> tuple[str, str | None]:
    settings = settings or get_settings()
    post = db.get(Post, post_id)
    if post is None:
        return "failed", f"post {post_id} not found"

    provider = get_embedding_provider(settings)
    text = f"{post.title}\n{post.body}"
    result = provider.embed(text)
    post.embedding = result.vector
    db.commit()
    log_call(
        db,
        provider=provider.name,
        task_type="embedding",
        related_type="post",
        related_id=post.id,
        units=result.units,
        cost_usd=result.cost_usd,
    )
    return "succeeded", None
