from __future__ import annotations

import httpx

from app.config import Settings
from app.embeddings.base import EmbeddingProvider, EmbeddingResult


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Fully local $0 alternative (e.g. `ollama pull all-minilm`)."""

    name = "ollama"

    def __init__(self, settings: Settings):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_embedding_model
        self._client = httpx.Client(timeout=60.0)

    def embed(self, text: str) -> EmbeddingResult:
        resp = self._client.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
        )
        resp.raise_for_status()
        vector = resp.json()["embedding"]
        return EmbeddingResult(vector=vector, units=len(text), cost_usd=0.0)
