from __future__ import annotations

from app.config import Settings
from app.embeddings.base import EmbeddingProvider


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "gemini":
        from app.embeddings.gemini_embeddings import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(settings)
    if settings.embedding_provider == "ollama":
        from app.embeddings.ollama_embeddings import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(settings)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}")
