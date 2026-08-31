"""Central configuration, loaded from environment variables / .env.

Kept as a single Pydantic settings object so every module reads config the
same way, and so the free-tier constraints from the capstone brief (no
credit card, stay in the free tier, keys only in .env) are enforced in one
place.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql+psycopg2://capstone:capstone@localhost:5432/capstone"

    # --- Vision / embedding provider ---
    # "gemini" (free tier, needs GEMINI_API_KEY) or "ollama" (fully local, no key)
    vision_provider: str = "gemini"
    embedding_provider: str = "gemini"

    gemini_api_key: str | None = None
    gemini_vision_model: str = "gemini-3.1-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"

    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "moondream"
    ollama_embedding_model: str = "all-minilm"

    # --- Mismatch guard thresholds (tuned against the eval set, see docs/DESIGN.md) ---
    # Vision confidence below this is flagged, never silently trusted. Calibrated
    # against the real run of the 50-image corpus (Gemini reported 0.88-1.0;
    # 0.93 flags the handful of genuinely hedgy identifications -- e.g. a wolf
    # photo the model itself called "grey wolf" at 0.88 -- without flagging the
    # clear majority). See DESIGN.md "Threshold calibration".
    vision_confidence_threshold: float = 0.93
    # Cosine similarity below this means "no confident match". Calibrated
    # against the real run: gemini-embedding-001 puts *any* two pieces of
    # English text (even an unrelated "cloud infra cost report" post
    # against animal photo captions) around 0.66-0.71 cosine similarity --
    # embeddings alone are not very discriminative at this corpus scale, so
    # the category-keyword check in app/guard.py does most of the real
    # work. 0.715 sits just above the best an off-topic post can reach
    # (0.710 observed) and just below the accepted-match floor for every
    # real category post (0.720+ observed, worst case the "dog" category).
    # See DESIGN.md "Threshold calibration".
    similarity_threshold: float = 0.715

    # --- Batch processing ---
    batch_max_retries: int = 3
    batch_retry_backoff_seconds: float = 1.5
    batch_max_workers: int = 4

    # --- Approx free-tier pricing used for cost tracking (USD), see docs/DESIGN.md ---
    gemini_vision_cost_per_call: float = 0.0  # Flash free tier: $0 within free-tier quota
    gemini_embedding_cost_per_call: float = 0.0

    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
