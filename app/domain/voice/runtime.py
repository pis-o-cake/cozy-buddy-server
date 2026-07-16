"""음성 파이프라인 provider 런타임 — 프로세스당 1회 초기화·상주 (설계서 §13-2).

cold load(모델 적재 수 초)를 발화 경로에서 제거하기 위해 최초 1회만 initialize하고
이후 재사용한다. 테스트는 reset_runtime()으로 격리한다.
"""

import asyncio

# provider 등록 트리거 — 새 구현 추가 시 여기에 import 한 줄
import app.domain.voice.providers.stt_faster_whisper  # noqa: F401
import app.domain.voice.providers.tts_supertonic  # noqa: F401
from app.domain.llm.factory import build_llm
from app.domain.llm.providers.base import LLMProvider
from app.domain.voice.factory import build_stt, build_tts
from app.domain.voice.providers.stt_base import STTProvider
from app.domain.voice.providers.tts_base import TTSProvider

_lock = asyncio.Lock()
_stt: STTProvider | None = None
_tts: TTSProvider | None = None
_llm: LLMProvider | None = None


async def get_stt() -> STTProvider:
    global _stt
    async with _lock:
        if _stt is None:
            provider = build_stt()
            await provider.initialize()
            _stt = provider
    return _stt


async def get_tts() -> TTSProvider:
    global _tts
    async with _lock:
        if _tts is None:
            provider = build_tts()
            await provider.initialize()
            _tts = provider
    return _tts


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = build_llm()
    return _llm


def reset_runtime() -> None:
    """테스트 전용 — 캐시된 provider를 버린다."""
    global _stt, _tts, _llm
    _stt = None
    _tts = None
    _llm = None
