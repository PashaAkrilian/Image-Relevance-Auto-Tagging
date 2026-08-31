from __future__ import annotations

import time

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.cost_tracker import log_call
from app.models import Image, TagStatus
from app.schemas import VisionTagSchema
from app.vision.factory import get_vision_provider


def process_one_image(db: Session, image_id: int, settings: Settings | None = None) -> tuple[str, str | None]:
    """Classify one image and durably settle its tag_status.

    A schema-validation failure is NOT surfaced as a job failure: it is
    retried against the model a few times (models are occasionally sloppy
    with JSON), and if it never conforms, the image is marked INVALID and
    excluded from every downstream step. That is the "never trust invalid
    model output" requirement, made concrete.
    """
    settings = settings or get_settings()
    provider = get_vision_provider(settings)

    image = db.get(Image, image_id)
    if image is None:
        return "failed", f"image {image_id} not found"

    last_error: str | None = None
    for attempt in range(1, settings.batch_max_retries + 1):
        result = provider.classify_image(image.file_path)
        log_call(
            db,
            provider=provider.name,
            task_type="vision",
            related_type="image",
            related_id=image.id,
            units=result.units,
            cost_usd=result.cost_usd,
        )
        try:
            parsed = VisionTagSchema.model_validate_json(result.raw_text)
        except ValidationError as exc:
            last_error = f"schema validation failed on attempt {attempt}: {exc}"
            if attempt < settings.batch_max_retries:
                time.sleep(settings.batch_retry_backoff_seconds * attempt)
            continue

        image.subject = parsed.subject
        image.tag_category = parsed.category
        image.attributes = parsed.attributes
        image.caption = parsed.caption
        image.confidence = parsed.confidence
        image.tag_status = (
            TagStatus.FLAGGED if parsed.confidence < settings.vision_confidence_threshold else TagStatus.VALID
        )
        image.tag_error = None
        db.commit()
        return "succeeded", None

    # Exhausted retries without ever getting schema-valid output: never trust it.
    image.tag_status = TagStatus.INVALID
    image.tag_error = last_error
    db.commit()
    return "succeeded", last_error
