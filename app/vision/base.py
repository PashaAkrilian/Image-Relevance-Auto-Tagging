from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VisionCallResult:
    """Raw provider output plus accounting, before schema validation."""

    raw_text: str
    units: int  # tokens (Gemini) or a proxy count (Ollama)
    cost_usd: float


class VisionProvider(ABC):
    """Common interface so the batch runner doesn't care whether tags come
    from Gemini Flash (cloud, free tier) or Ollama (fully local)."""

    name: str

    @abstractmethod
    def classify_image(self, image_path: str) -> VisionCallResult:
        """Send one image to the vision model and return its raw text
        response. Callers are responsible for JSON-parsing + schema
        validation -- this layer never trusts the output either."""
        raise NotImplementedError
