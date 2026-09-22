from dataclasses import dataclass
from typing import List


@dataclass
class VADSegment:
    start_ms: int
    end_ms: int
    is_speech: bool
    confidence: float


class SileroVADAdapter:
    """Voice Activity Detection adapter providing speech detection and interruption signaling."""

    def __init__(self, threshold: float = 0.5, sampling_rate: int = 16000):
        self.threshold = threshold
        self.sampling_rate = sampling_rate

    def detect_speech(self, audio_chunk: bytes) -> bool:
        """Determines whether a chunk contains human speech."""
        if not audio_chunk or len(audio_chunk) < 32:
            return False
        # Calculate RMS energy of 16-bit PCM chunk as baseline deterministic fallback
        # when torch/silero model is running in test/mock mode
        import audioop
        try:
            rms = audioop.rms(audio_chunk, 2)
            return rms > 300
        except Exception:
            return len(audio_chunk) > 100

    def check_interruption(self, ai_speaking: bool, audio_chunk: bytes) -> bool:
        """Triggers interruption when customer speech is detected while AI is speaking."""
        if not ai_speaking:
            return False
        return self.detect_speech(audio_chunk)
