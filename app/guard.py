"""The mismatch guard: the production-critical safety layer (brief section
4.3). Combines the model's own extracted tags, the embedding similarity
score, and confidence to decide "is this recommendation actually good
enough?" -- and always returns a human-readable reason, whether it accepts,
rejects, or says "no confident match".

Deliberately pure / DB-free so it's directly unit-testable (see
tests/test_guard.py) against the exact fox/wolf scenario from the brief.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical category -> keyword variants (plurals, common names, one
# scientific name) used both to read the "expected subject" out of a post's
# text and to canonicalize whatever the vision model detected. This is what
# lets "red foxes", "fox", and "Vulpes vulpes" all resolve to the same
# category (brief: "match concepts, not exact words").
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "fox": ["fox", "foxes", "vulpes vulpes", "red fox"],
    "wolf": ["wolf", "wolves", "canis lupus", "gray wolf", "grey wolf"],
    "dog": ["dog", "dogs", "puppy", "puppies", "canis familiaris", "domestic dog"],
    "bear": ["bear", "bears", "ursus arctos", "brown bear", "grizzly"],
    "deer": ["deer", "stag", "doe", "cervus elaphus", "red deer"],
}


def _canonicalize(text: str | None) -> str | None:
    if not text:
        return None
    low = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", low):
                return category
    return None


def extract_expected_category(post_title: str, post_body: str) -> str | None:
    """Best-effort subject extraction from post text. Returns None if no
    known category keyword is present (guard then falls back to
    similarity-only screening for that post)."""
    return _canonicalize(f"{post_title} {post_body}")


@dataclass
class ImageCandidate:
    image_id: int
    tag_status: str  # "valid" | "flagged" | "invalid" | "pending"
    subject: str | None
    tag_category: str | None
    similarity: float


@dataclass
class GuardDecision:
    image_id: int | None
    status: str  # "accepted" | "rejected" | "no_match"
    reason: str
    similarity: float | None
    rank: int | None


def evaluate_candidate(
    expected_category: str | None,
    candidate: ImageCandidate,
    similarity_threshold: float,
) -> GuardDecision:
    if candidate.tag_status == "invalid":
        return GuardDecision(
            image_id=candidate.image_id,
            status="rejected",
            reason="Vision output for this image never validated against the tag schema; invalid output is never trusted.",
            similarity=candidate.similarity,
            rank=None,
        )

    detected_category = _canonicalize(candidate.subject) or _canonicalize(candidate.tag_category)

    if expected_category is not None:
        if detected_category is None:
            return GuardDecision(
                image_id=candidate.image_id,
                status="rejected",
                reason=(
                    f"Post expects subject '{expected_category}' but the candidate's detected subject "
                    f"('{candidate.subject}') doesn't resolve to a known category; refusing an unverifiable match."
                ),
                similarity=candidate.similarity,
                rank=None,
            )
        if detected_category != expected_category:
            return GuardDecision(
                image_id=candidate.image_id,
                status="rejected",
                reason=f"Category mismatch: expected {expected_category}, detected {detected_category}.",
                similarity=candidate.similarity,
                rank=None,
            )

    if candidate.similarity < similarity_threshold:
        return GuardDecision(
            image_id=candidate.image_id,
            status="rejected",
            reason=(
                f"Similarity {candidate.similarity:.2f} is below the {similarity_threshold:.2f} confidence bar."
            ),
            similarity=candidate.similarity,
            rank=None,
        )

    reason = f"Category and similarity both clear the bar (similarity {candidate.similarity:.2f})."
    if candidate.tag_status == "flagged":
        reason += " Note: this image's own tags were low-confidence and flagged for human review."

    return GuardDecision(
        image_id=candidate.image_id,
        status="accepted",
        reason=reason,
        similarity=candidate.similarity,
        rank=None,
    )


def run_guard(
    post_title: str,
    post_body: str,
    candidates: list[ImageCandidate],
    similarity_threshold: float,
) -> list[GuardDecision]:
    """Evaluate every candidate for a post and return a fully ranked
    decision list: accepted candidates first (ranked 1..N by similarity),
    then rejected ones, then -- if nothing was accepted -- a trailing
    'no_match' placeholder explaining why."""
    expected_category = extract_expected_category(post_title, post_body)

    decisions = [
        evaluate_candidate(expected_category, c, similarity_threshold)
        for c in sorted(candidates, key=lambda c: c.similarity, reverse=True)
    ]

    accepted = [d for d in decisions if d.status == "accepted"]
    rejected = [d for d in decisions if d.status == "rejected"]
    accepted.sort(key=lambda d: d.similarity or 0.0, reverse=True)
    for i, d in enumerate(accepted, start=1):
        d.rank = i

    if accepted:
        return accepted + rejected

    best_similarity = max((c.similarity for c in candidates), default=0.0)
    no_match = GuardDecision(
        image_id=None,
        status="no_match",
        reason=(
            f"No confident match: no candidate cleared both the category check and the "
            f"{similarity_threshold:.2f} similarity threshold (best similarity seen was {best_similarity:.2f})."
            if candidates
            else "No confident match: no candidate images available."
        ),
        similarity=None,
        rank=None,
    )
    return [no_match] + rejected
