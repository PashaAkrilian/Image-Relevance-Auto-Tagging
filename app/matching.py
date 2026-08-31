"""Cosine similarity ranking between a post's embedding and every image's
embedding. Pure numpy, no external vector DB needed at ~50 images (brief
section 10: "in-DB arrays fine at this scale")."""
from __future__ import annotations

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def rank_images(post_embedding: list[float], images: list[tuple[int, list[float]]]) -> list[tuple[int, float]]:
    """Return [(image_id, similarity)] sorted by similarity descending."""
    scored = [(image_id, cosine_similarity(post_embedding, vec)) for image_id, vec in images]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored
