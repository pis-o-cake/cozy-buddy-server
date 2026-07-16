"""voice provider 팩토리 (설계서 §3-2).

Phase 1에서 faster-whisper/Supertonic 구현체가 각 레지스트리에 등록된다.
등록 전에는 build 시 ProviderNotFoundError로 명확히 실패한다.
"""

from app.config import Settings, get_settings
from app.core.registry import ProviderRegistry
from app.domain.voice.providers.stt_base import STTProvider
from app.domain.voice.providers.tts_base import TTSProvider

stt_registry: ProviderRegistry[STTProvider] = ProviderRegistry("stt")
tts_registry: ProviderRegistry[TTSProvider] = ProviderRegistry("tts")


def build_stt(settings: Settings | None = None) -> STTProvider:
    settings = settings or get_settings()
    return stt_registry.build(settings.stt_provider)


def build_tts(settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    return tts_registry.build(settings.tts_provider)
