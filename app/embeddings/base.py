from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    vector: list[float]
    units: int
    cost_usd: float


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult:
        raise NotImplementedError
