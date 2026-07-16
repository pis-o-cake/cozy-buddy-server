"""Supertonic TTS provider (설계서 §3-3 — 기본 TTS, 한국어 네이티브).

공식 PyPI 패키지(supertonic)의 TTS 클래스를 사용한다. 첫 실행 시 모델(~260MB)을
자동 다운로드한다. 비스트리밍 엔진이지만 문장 단위 합성→즉시 yield로 체감 지연을
최소화한다 (§4 파이프라인 규약 — 문장 분리는 voice 서비스 담당).

라이선스: 모델은 OpenRAIL-M — 자가호스팅 무방, 외부 배포 시 조항 재검토 (§13-3).
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from loguru import logger

from app.config import Settings, get_settings
from app.domain.voice.factory import tts_registry
from app.domain.voice.providers.tts_base import AudioChunk, TTSCapabilities, TTSProvider

_FALLBACK_SAMPLE_RATE = 44100
_CHUNK_SAMPLES = 4800  # 다운링크 프레이밍 단위 (rate와 무관한 고정 청크)


@tts_registry.register("supertonic")
class SupertonicTTS(TTSProvider):
    name: ClassVar[str] = "supertonic"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._tts: Any = None
        self._style: Any = None
        self._rate: int = _FALLBACK_SAMPLE_RATE

    async def initialize(self) -> None:
        if self._tts is not None:
            return
        voice = self._settings.tts_voice

        def _load() -> tuple[Any, Any, int]:
            from supertonic import TTS  # 지연 import (voice extra)

            tts = TTS(auto_download=True)
            style = tts.get_voice_style(voice_name=voice)
            rate = int(getattr(tts, "sample_rate", _FALLBACK_SAMPLE_RATE))
            return tts, style, rate

        self._tts, self._style, self._rate = await asyncio.to_thread(_load)
        logger.info("tts model loaded: supertonic (voice={}, rate={})", voice, self._rate)

    async def synthesize_stream(
        self, text: str, *, voice: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        if self._tts is None:
            await self.initialize()

        def _run() -> bytes:
            import numpy as np

            style = self._tts.get_voice_style(voice_name=voice) if voice else self._style
            wav, _duration = self._tts.synthesize(text, voice_style=style)
            samples = np.asarray(wav).reshape(-1)
            # float(-1~1) → PCM16 (WS 바이너리 0x02 페이로드 — §5-1)
            if samples.dtype.kind == "f":
                samples = np.clip(samples, -1.0, 1.0)
                samples = (samples * 32767.0).astype(np.int16)
            return samples.astype("<i2").tobytes()

        pcm = await asyncio.to_thread(_run)
        step = _CHUNK_SAMPLES * 2  # int16
        for offset in range(0, len(pcm), step):
            chunk = pcm[offset : offset + step]
            yield AudioChunk(pcm=chunk, rate=self._rate, is_last=offset + step >= len(pcm))

    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(streaming=False)

    async def shutdown(self) -> None:
        self._tts = None
        self._style = None
