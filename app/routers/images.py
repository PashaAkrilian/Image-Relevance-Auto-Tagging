from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.jobs.embedding_job import process_one_image_embedding
from app.jobs.runner import run_batch
from app.jobs.vision_job import process_one_image
from app.models import Image, TagStatus
from app.schemas import ImageOut

router = APIRouter(prefix="/images", tags=["images"])


@router.get("", response_model=list[ImageOut])
def list_images(db: Session = Depends(get_db), tag_status: str | None = None):
    q = db.query(Image)
    if tag_status:
        q = q.filter(Image.tag_status == TagStatus(tag_status))
    return q.order_by(Image.id).all()


@router.get("/{image_id}", response_model=ImageOut)
def get_image(image_id: int, db: Session = Depends(get_db)):
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="image not found")
    return image


@router.post("/batch/classify")
def trigger_vision_batch(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Kick off the vision batch job (structured tagging) as a background
    task -- returns immediately, never blocks the request."""
    image_ids = [row.id for row in db.query(Image.id).all()]
    if not image_ids:
        raise HTTPException(status_code=400, detail="no images to classify; run the seed script first")

    def _run():
        run_batch(
            job_type="vision",
            item_type="image",
            item_ids=image_ids,
            process_one=lambda db_, iid: process_one_image(db_, iid, settings),
            settings=settings,
        )

    background_tasks.add_task(_run)
    return {"status": "started", "queued_images": len(image_ids)}


@router.post("/batch/embed")
def trigger_embedding_batch(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    image_ids = [
        row.id
        for row in db.query(Image.id).filter(Image.tag_status != TagStatus.INVALID).all()
    ]
    if not image_ids:
        raise HTTPException(status_code=400, detail="no eligible images to embed; run vision classification first")

    def _run():
        run_batch(
            job_type="embedding",
            item_type="image",
            item_ids=image_ids,
            process_one=lambda db_, iid: process_one_image_embedding(db_, iid, settings),
            settings=settings,
        )

    background_tasks.add_task(_run)
    return {"status": "started", "queued_images": len(image_ids)}
