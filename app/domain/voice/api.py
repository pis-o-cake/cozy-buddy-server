"""Voice domain API router."""

from fastapi import APIRouter, UploadFile
from fastapi.responses import Response

from app.domain.voice.schemas import STTResponse, TTSRequest
from app.domain.voice.stt_service import STTService
from app.domain.voice.tts_service import TTSService

router = APIRouter()

stt_service = STTService()
tts_service = TTSService()


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile) -> STTResponse:
    """Convert speech to text."""
    audio_data = await file.read()
    return await stt_service.transcribe(audio_data)


@router.post("/tts")
async def text_to_speech(request: TTSRequest) -> Response:
    """Convert text to speech."""
    audio = await tts_service.synthesize(request.text, speed=request.speed)
    return Response(content=audio, media_type="audio/wav")
