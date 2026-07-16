"""STTProvider 계약 (설계서 §3-2). 구현체(faster-whisper 등)는 Phase 1."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class STTResult:
    text: str
    confidence: float  # 저신뢰 되묻기 정책(§12-1) 판단용
    duration_ms: int


@dataclass
class STTPartial:
    text: str


class STTProvider(ABC):
    name: ClassVar[str] = ""

    @abstractmethod
    async def initialize(self) -> None:
        """모델 적재 등 무거운 초기화. 앱 lifespan에서 1회 호출 (cold load 회피 — §13-2)."""

    @abstractmethod
    async def transcribe(
        self,
        pcm: bytes,
        *,
        rate: int = 16000,
        lang: str = "ko",
        initial_prompt: str | None = None,
    ) -> STTResult:
        """발화 단위 일괄 전사.

        Args:
            initial_prompt: 기기명·방 이름 주입용 — 고유명사 인식률 개선 (§3-2).
        """

    async def transcribe_stream(
        self,
        frames: AsyncIterator[bytes],
        *,
        rate: int = 16000,
        lang: str = "ko",
        on_partial: Callable[[STTPartial], Awaitable[None]] | None = None,
    ) -> STTResult:
        """기본 구현: 프레임을 버퍼링한 뒤 transcribe()에 위임 (partial 미발화).

        CLOVA gRPC 등 진짜 스트리밍 provider가 override한다 — 인터페이스에 미리 정의해
        교체 시 게이트웨이 수정이 없도록 한다 (§3-2).
        """
        buffer = bytearray()
        async for frame in frames:
            buffer.extend(frame)
        return await self.transcribe(bytes(buffer), rate=rate, lang=lang)

    @abstractmethod
    async def shutdown(self) -> None: ...
