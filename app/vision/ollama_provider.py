from __future__ import annotations

import base64
import json

import httpx

from app.config import Settings
from app.vision.base import VisionCallResult, VisionProvider

PROMPT = (
    "Look at this image and respond ONLY with JSON: "
    '{"subject": str, "category": str, "attributes": [str], "caption": str, "confidence": 0-1 float}. '
    "confidence is your own honest certainty about the subject identification."
)


class OllamaVisionProvider(VisionProvider):
    """Fully local, $0, no-API-key alternative to Gemini (brief section 10).

    Not exercised in this repo's committed evidence run (no local GPU/Ollama
    install in the build environment) but wired end-to-end and selectable via
    VISION_PROVIDER=ollama for anyone running this off the cloud path.
    """

    name = "ollama"

    def __init__(self, settings: Settings):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_vision_model
        self._client = httpx.Client(timeout=120.0)

    def classify_image(self, image_path: str) -> VisionCallResult:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        resp = self._client.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": PROMPT,
                "images": [b64],
                "format": "json",
                "stream": False,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        text = body.get("response", "")
        # Ollama doesn't bill tokens, but report eval_count as a size proxy for parity.
        units = int(body.get("eval_count") or 0)
        return VisionCallResult(raw_text=text, units=units, cost_usd=0.0)
