"""faster-whisper STT provider (설계서 §3-3 — 기본 STT).

- compute_type은 float16 고정 권장: RTX 5080(Blackwell)은 CTranslate2 INT8 미지원.
- 의존성(faster-whisper·numpy)은 `pip install -e ".[voice]"` — 지연 import로
  미설치 환경(테스트)에서도 모듈 로드는 가능하게 유지한다.
"""

import asyncio
import math
import time
from typing import Any, ClassVar

from loguru import logger

from app.config import Settings, get_settings
from app.domain.voice.factory import stt_registry
from app.domain.voice.providers.stt_base import STTProvider, STTResult


@stt_registry.register("faster-whisper")
class FasterWhisperSTT(STTProvider):
    name: ClassVar[str] = "faster-whisper"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model: Any = None

    async def initialize(self) -> None:
        if self._model is not None:
            return
        settings = self._settings

        def _load() -> Any:
            from faster_whisper import WhisperModel  # 지연 import (voice extra)

            try:
                return WhisperModel(
                    settings.stt_model, device="cuda", compute_type=settings.stt_compute_type
                )
            except (RuntimeError, ValueError) as exc:
                logger.warning("cuda unavailable for stt, falling back to cpu: {}", exc)
                return WhisperModel(settings.stt_model, device="cpu", compute_type="int8")

        # 모델 적재는 수 초 — 이벤트 루프를 막지 않는다
        self._model = await asyncio.to_thread(_load)
        logger.info("stt model loaded: {} ({})", settings.stt_model, settings.stt_compute_type)

    async def transcribe(
        self,
        pcm: bytes,
        *,
        rate: int = 16000,
        lang: str = "ko",
        initial_prompt: str | None = None,
    ) -> STTResult:
        if self._model is None:
            await self.initialize()

        def _run() -> STTResult:
            import numpy as np

            started = time.perf_counter()
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _info = self._model.transcribe(
                audio,
                language=lang,
                vad_filter=True,  # 무음 환각 방어 (§12-1)
                initial_prompt=initial_prompt,
            )
            texts: list[str] = []
            logprobs: list[float] = []
            for segment in segments:
                texts.append(segment.text)
                logprobs.append(segment.avg_logprob)
            text = "".join(texts).strip()
            # avg_logprob 평균 → 0~1 신뢰도 근사 (되묻기 임계 판정용 — §12-1)
            confidence = math.exp(sum(logprobs) / len(logprobs)) if logprobs else 0.0
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return STTResult(text=text, confidence=min(confidence, 1.0), duration_ms=elapsed_ms)

        return await asyncio.to_thread(_run)

    async def shutdown(self) -> None:
        self._model = None
