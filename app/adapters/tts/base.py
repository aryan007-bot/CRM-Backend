from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TTSResult:
    audio_data: bytes
    sample_rate: int
    duration_seconds: float
    format: str


class BaseTTSAdapter(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_profile_path: Optional[str] = None,
        language: str = "en-IN",
    ) -> TTSResult:
        pass

    @abstractmethod
    def health_check(self) -> dict:
        pass
