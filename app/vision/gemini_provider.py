from __future__ import annotations

import mimetypes

from google import genai
from google.genai import types

from app.config import Settings
from app.schemas import VisionTagSchema
from app.vision.base import VisionCallResult, VisionProvider

PROMPT = (
    "Look at this image and describe it for a content-matching system. "
    "Respond ONLY as JSON matching the schema: subject (the specific "
    "thing shown, e.g. 'red fox'), category (broad category, e.g. "
    "'animal'), attributes (3-6 short descriptive tags), caption (one "
    "plain sentence describing the image), confidence (0-1, your own "
    "honest certainty about the subject identification -- use a lower "
    "number if the species/subject is ambiguous or you are guessing)."
)


class GeminiVisionProvider(VisionProvider):
    name = "gemini"

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set; cannot use the gemini vision provider.")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_vision_model
        self._cost_per_call = settings.gemini_vision_cost_per_call

    def classify_image(self, image_path: str) -> VisionCallResult:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            data = f.read()

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime_type),
                PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VisionTagSchema,
                temperature=0.1,
            ),
        )

        text = response.text or ""
        units = 0
        if response.usage_metadata is not None:
            units = response.usage_metadata.total_token_count or 0

        return VisionCallResult(raw_text=text, units=units, cost_usd=self._cost_per_call)
