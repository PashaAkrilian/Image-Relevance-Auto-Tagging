"""The exact scenario from the brief (section 4.3 / PROBE 2, 3, 4):
fox post ranks the fox image first, and provably rejects the wolf."""
from __future__ import annotations

from app.guard import ImageCandidate, extract_expected_category, run_guard

POST_TITLE = "The behavior of red foxes"
POST_BODY = "Red foxes are solitary, adaptable hunters found across the northern hemisphere."


def test_extract_expected_category_reads_fox_from_post_text():
    assert extract_expected_category(POST_TITLE, POST_BODY) == "fox"


def test_extract_expected_category_none_when_no_known_subject():
    assert extract_expected_category("Quarterly sales results", "Revenue grew 12% year over year.") is None


def test_guard_rejects_wolf_candidate_on_fox_post():
    """PROBE 3: force the wolf as a candidate for the fox post -> the guard
    rejects it with a category-mismatch explanation."""
    candidates = [
        ImageCandidate(image_id=1, tag_status="valid", subject="gray wolf", tag_category="animal", similarity=0.91),
    ]
    decisions = run_guard(POST_TITLE, POST_BODY, candidates, similarity_threshold=0.55)
    # Nothing was accepted, so the guard leads with a "no_match" placeholder,
    # followed by the wolf candidate's own rejection record.
    assert decisions[0].status == "no_match"
    rejected = [d for d in decisions if d.image_id == 1]
    assert len(rejected) == 1
    assert rejected[0].status == "rejected"
    assert "mismatch" in rejected[0].reason.lower()
    assert "fox" in rejected[0].reason and "wolf" in rejected[0].reason


def test_guard_accepts_fox_candidate_and_ranks_it_first():
    """PROBE 2: fox image ranks first, wolf and dog rank clearly lower
    (here: rejected outright, since they fail the category check)."""
    candidates = [
        ImageCandidate(image_id=1, tag_status="valid", subject="red fox", tag_category="animal", similarity=0.88),
        ImageCandidate(image_id=2, tag_status="valid", subject="gray wolf", tag_category="animal", similarity=0.83),
        ImageCandidate(image_id=3, tag_status="valid", subject="domestic dog", tag_category="animal", similarity=0.40),
    ]
    decisions = run_guard(POST_TITLE, POST_BODY, candidates, similarity_threshold=0.55)

    accepted = [d for d in decisions if d.status == "accepted"]
    assert len(accepted) == 1
    assert accepted[0].image_id == 1
    assert accepted[0].rank == 1

    rejected_ids = {d.image_id for d in decisions if d.status == "rejected"}
    assert rejected_ids == {2, 3}


def test_guard_no_confident_match_when_nothing_clears_the_bar():
    """PROBE 4: query a post with no suitable image -> 'no confident
    match' with reasons (similarity below threshold / subjects don't
    match), never a guessed answer."""
    candidates = [
        ImageCandidate(image_id=1, tag_status="valid", subject="gray wolf", tag_category="animal", similarity=0.20),
    ]
    decisions = run_guard(POST_TITLE, POST_BODY, candidates, similarity_threshold=0.55)
    assert decisions[0].status == "no_match"
    assert decisions[0].image_id is None
    assert "no confident match" in decisions[0].reason.lower()


def test_guard_never_trusts_invalid_tag_status():
    candidates = [
        ImageCandidate(image_id=1, tag_status="invalid", subject=None, tag_category=None, similarity=0.95),
    ]
    decisions = run_guard(POST_TITLE, POST_BODY, candidates, similarity_threshold=0.55)
    assert decisions[0].status in ("rejected", "no_match")
    assert all(d.image_id != 1 or d.status == "rejected" for d in decisions)


def test_guard_flags_low_confidence_note_but_can_still_accept():
    candidates = [
        ImageCandidate(image_id=1, tag_status="flagged", subject="red fox", tag_category="animal", similarity=0.70),
    ]
    decisions = run_guard(POST_TITLE, POST_BODY, candidates, similarity_threshold=0.55)
    assert decisions[0].status == "accepted"
    assert "low-confidence" in decisions[0].reason.lower()


def test_guard_rejects_below_similarity_threshold_even_with_matching_category():
    candidates = [
        ImageCandidate(image_id=1, tag_status="valid", subject="red fox", tag_category="animal", similarity=0.30),
    ]
    decisions = run_guard(POST_TITLE, POST_BODY, candidates, similarity_threshold=0.55)
    assert decisions[0].status == "no_match" or (decisions[0].status == "rejected" and "similarity" in decisions[0].reason.lower())
