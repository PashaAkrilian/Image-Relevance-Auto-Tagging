from __future__ import annotations

from google import genai
from google.genai import types

from app.config import Settings
from app.embeddings.base import EmbeddingProvider, EmbeddingResult


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set; cannot use the gemini embedding provider.")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_embedding_model
        self._cost_per_call = settings.gemini_embedding_cost_per_call

    def embed(self, text: str) -> EmbeddingResult:
        result = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
        )
        vector = list(result.embeddings[0].values)
        # The embed API doesn't return token usage; approximate with char count
        # for the cost log so every call still gets an accounting row.
        units = len(text)
        return EmbeddingResult(vector=vector, units=units, cost_usd=self._cost_per_call)
