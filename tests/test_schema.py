"""Structured vision output must validate against the schema; anything
that doesn't is never trusted downstream (requirement: 'AI processing')."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import VisionTagSchema


def test_valid_payload_parses():
    payload = {
        "subject": "red fox",
        "category": "animal",
        "attributes": ["orange fur", "wild", "forest"],
        "caption": "A red fox standing in a forest",
        "confidence": 0.94,
    }
    tag = VisionTagSchema.model_validate(payload)
    assert tag.subject == "red fox"
    assert tag.confidence == pytest.approx(0.94)


@pytest.mark.parametrize(
    "payload",
    [
        {"subject": "red fox", "category": "animal", "attributes": [], "caption": "x"},  # missing confidence
        {"subject": "red fox", "category": "animal", "attributes": [], "caption": "x", "confidence": 1.4},  # out of range
        {"subject": "red fox", "category": "animal", "attributes": [], "caption": "x", "confidence": "high"},  # wrong type
        {"subject": "", "category": "animal", "attributes": [], "caption": "x", "confidence": 0.5},  # empty subject
    ],
)
def test_invalid_payloads_are_rejected(payload):
    with pytest.raises(ValidationError):
        VisionTagSchema.model_validate(payload)


def test_malformed_json_never_parses():
    with pytest.raises(ValidationError):
        VisionTagSchema.model_validate_json("not json at all")


def test_attributes_are_trimmed_and_capped():
    payload = {
        "subject": "red fox",
        "category": "animal",
        "attributes": ["  orange fur  ", "", "wild"],
        "caption": "A red fox",
        "confidence": 0.8,
    }
    tag = VisionTagSchema.model_validate(payload)
    assert tag.attributes == ["orange fur", "wild"]
