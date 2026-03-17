"""Wake word detection service."""

from loguru import logger


class WakeWordService:
    """OpenWakeWord based wake word detection service."""

    def __init__(self) -> None:
        self._model = None
        self._is_listening = False

    async def initialize(self) -> None:
        """Load model."""
        # TODO: Load OpenWakeWord model
        logger.info("Wake word model initialized")

    async def detect(self, audio_chunk: bytes) -> bool:
        """Detect wake word."""
        # TODO: OpenWakeWord inference
        return False
