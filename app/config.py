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
    gemini_vision_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "moondream"
    ollama_embedding_model: str = "all-minilm"

    # --- Mismatch guard thresholds (tuned against the eval set, see docs/DESIGN.md) ---
    # Vision confidence below this is flagged, never silently trusted.
    vision_confidence_threshold: float = 0.60
    # Cosine similarity below this means "no confident match".
    similarity_threshold: float = 0.55

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
