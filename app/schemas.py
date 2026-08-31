"""Pydantic schemas.

`VisionTagSchema` is the contract every vision-model response must satisfy.
It is used both to ask Gemini for structured output (response_schema) and to
validate whatever comes back before anything downstream is allowed to trust
it (requirement: "Vision model produces structured output validated against
a schema; invalid responses are never trusted").
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VisionTagSchema(BaseModel):
    subject: str = Field(..., min_length=1, max_length=128, description="The specific thing shown, e.g. 'red fox'")
    category: str = Field(..., min_length=1, max_length=64, description="Broad category, e.g. 'animal'")
    attributes: list[str] = Field(default_factory=list, max_length=12)
    caption: str = Field(..., min_length=1, max_length=512)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("attributes")
    @classmethod
    def _cap_attribute_length(cls, v: list[str]) -> list[str]:
        return [a.strip()[:64] for a in v if a and a.strip()]


class ImageOut(BaseModel):
    id: int
    category: str
    file_path: str
    subject: str | None
    tag_category: str | None
    attributes: list[str] | None
    caption: str | None
    confidence: float | None
    tag_status: str
    tag_error: str | None

    model_config = {"from_attributes": True}


class PostOut(BaseModel):
    id: int
    title: str
    body: str
    expected_category: str | None

    model_config = {"from_attributes": True}


class SuggestionOut(BaseModel):
    id: int
    post_id: int
    image_id: int | None
    similarity_score: float | None
    rank: int | None
    status: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PostSuggestionsResponse(BaseModel):
    post: PostOut
    suggestions: list[SuggestionOut]
    best_match: SuggestionOut | None


class ReviewDecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    note: str | None = None


class ReviewDecisionOut(BaseModel):
    id: int
    suggestion_id: int
    decision: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchJobOut(BaseModel):
    id: int
    job_type: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class CostSummaryRow(BaseModel):
    provider: str
    task_type: str
    calls: int
    total_units: int
    total_cost_usd: float


class CostSummaryResponse(BaseModel):
    rows: list[CostSummaryRow]
    total_cost_usd: float
    total_calls: int
