from __future__ import annotations

import logging

from fastapi import FastAPI

from app.routers import batch, costs, images, posts, review

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Image Understanding & Content Matching Engine",
    description=(
        "Tags an image library with a vision model, embeds images and blog "
        "posts into a shared semantic space, ranks candidates per post, and "
        "runs every candidate through a mismatch guard before a human ever "
        "sees it."
    ),
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(images.router)
app.include_router(posts.router)
app.include_router(review.router)
app.include_router(batch.router)
app.include_router(costs.router)
