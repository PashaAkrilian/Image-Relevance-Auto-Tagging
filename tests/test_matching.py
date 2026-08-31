from __future__ import annotations

import pytest

from app.matching import cosine_similarity, rank_images


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_is_zero_not_nan():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_rank_images_sorts_descending_by_similarity():
    query = [1.0, 0.0]
    images = [
        (1, [0.0, 1.0]),   # orthogonal -> 0.0
        (2, [1.0, 0.0]),   # identical -> 1.0
        (3, [0.7, 0.7]),   # ~0.707
    ]
    ranked = rank_images(query, images)
    assert [image_id for image_id, _ in ranked] == [2, 3, 1]
    assert ranked[0][1] == pytest.approx(1.0)
