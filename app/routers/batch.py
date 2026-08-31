from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BatchJob
from app.schemas import BatchJobOut

router = APIRouter(prefix="/batch", tags=["batch"])


@router.get("/jobs", response_model=list[BatchJobOut])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(BatchJob).order_by(BatchJob.id.desc()).all()


@router.get("/jobs/{job_id}", response_model=BatchJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(BatchJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
