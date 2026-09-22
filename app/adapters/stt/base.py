from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class STTResult:
    text: str
    is_final: bool
    confidence: float
    language: str
    duration_ms: int


class BaseSTTAdapter(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: str = "en-IN") -> STTResult:
        pass

    @abstractmethod
    def health_check(self) -> dict:
        pass
