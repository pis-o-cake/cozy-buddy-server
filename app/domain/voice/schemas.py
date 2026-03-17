"""Voice domain schemas."""

from pydantic import BaseModel, Field


class STTResponse(BaseModel):
    """STT response."""

    text: str
    language: str = "ko"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TTSRequest(BaseModel):
    """TTS request."""

    text: str = Field(..., min_length=1, description="Text to convert")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
