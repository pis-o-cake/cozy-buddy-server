"""STT (Speech-to-Text) service."""

from loguru import logger

from app.core.i18n import t
from app.domain.voice.schemas import STTResponse


class STTService:
    """Faster-Whisper based STT service."""

    def __init__(self) -> None:
        self._model = None

    async def initialize(self) -> None:
        """Load model."""
        # TODO: Load Faster-Whisper model
        logger.info("STT model initialized")

    async def transcribe(self, audio_data: bytes) -> STTResponse:
        """Convert speech to text."""
        # TODO: Faster-Whisper inference
        logger.info(f"STT processing: {len(audio_data)} bytes")
        return STTResponse(text=t("stub.stt_pending"), confidence=0.0)
