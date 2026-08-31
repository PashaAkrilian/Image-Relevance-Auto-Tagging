from __future__ import annotations

from app.config import Settings
from app.vision.base import VisionProvider


def get_vision_provider(settings: Settings) -> VisionProvider:
    if settings.vision_provider == "gemini":
        from app.vision.gemini_provider import GeminiVisionProvider

        return GeminiVisionProvider(settings)
    if settings.vision_provider == "ollama":
        from app.vision.ollama_provider import OllamaVisionProvider

        return OllamaVisionProvider(settings)
    raise ValueError(f"Unknown VISION_PROVIDER: {settings.vision_provider!r}")
