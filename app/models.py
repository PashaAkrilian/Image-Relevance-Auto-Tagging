from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TagStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    FLAGGED = "flagged"  # parsed & schema-valid, but low confidence -> needs human review
    INVALID = "invalid"  # model output never conformed to schema after retries -> never trusted


class SuggestionStatus(str, enum.Enum):
    ACCEPTED = "accepted"  # passed the mismatch guard, ranked as a candidate
    REJECTED = "rejected"  # guard rejected it (category mismatch / below threshold)
    NO_MATCH = "no_match"  # placeholder row: no candidate for this post cleared the bar


class ReviewDecisionValue(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"  # completed with some permanently-failed items


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64), index=True)  # corpus label, e.g. "red fox"
    file_path: Mapped[str] = mapped_column(String(512))
    source_url: Mapped[str] = mapped_column(String(1024))
    license: Mapped[str] = mapped_column(String(256), default="")

    # --- vision output (validated against app.schemas.VisionTagSchema) ---
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tag_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attributes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tag_status: Mapped[TagStatus] = mapped_column(
        Enum(TagStatus, name="tag_status"), default=TagStatus.PENDING, index=True
    )
    tag_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedding: Mapped[list | None] = mapped_column(ARRAY(Float), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="image")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    # Expected subject category, extracted from title/body text at seed time via keyword
    # matching (see scripts/seed_corpus.py). Used only by the eval script as ground truth,
    # never by the guard itself (the guard only ever sees image tags + embeddings).
    expected_category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    embedding: Mapped[list | None] = mapped_column(ARRAY(Float), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="post")


class Suggestion(Base):
    """One ranked (post, image) candidate pairing, after the mismatch guard has run."""

    __tablename__ = "suggestions"
    __table_args__ = (UniqueConstraint("post_id", "image_id", name="uq_post_image"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id"), nullable=True, index=True)

    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SuggestionStatus] = mapped_column(Enum(SuggestionStatus, name="suggestion_status"))
    reason: Mapped[str] = mapped_column(Text)  # human-readable guard explanation, always populated

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    post: Mapped["Post"] = relationship(back_populates="suggestions")
    image: Mapped["Image | None"] = relationship(back_populates="suggestions")
    review: Mapped["ReviewDecision | None"] = relationship(back_populates="suggestion", uselist=False)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    suggestion_id: Mapped[int] = mapped_column(ForeignKey("suggestions.id"), unique=True, index=True)
    decision: Mapped[ReviewDecisionValue] = mapped_column(Enum(ReviewDecisionValue, name="review_decision_value"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    suggestion: Mapped["Suggestion"] = relationship(back_populates="review")


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32))  # "vision" | "embedding"
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.PENDING)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    items: Mapped[list["BatchJobItem"]] = relationship(back_populates="job")


class BatchJobItem(Base):
    __tablename__ = "batch_job_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_job_id: Mapped[int] = mapped_column(ForeignKey("batch_jobs.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(32))  # "image" | "post"
    item_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_item_status"), default=JobStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["BatchJob"] = relationship(back_populates="items")


class ApiCallLog(Base):
    """Per-call cost tracking, required even inside a $0 free tier (requirement #7)."""

    __tablename__ = "api_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))  # "gemini" | "ollama"
    task_type: Mapped[str] = mapped_column(String(32))  # "vision" | "embedding"
    related_type: Mapped[str] = mapped_column(String(32))  # "image" | "post"
    related_id: Mapped[int] = mapped_column(Integer)
    units: Mapped[int] = mapped_column(Integer, default=0)  # tokens/chars, provider-reported when available
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
