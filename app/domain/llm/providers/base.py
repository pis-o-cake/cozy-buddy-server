"""LLMProvider 계약 (설계서 §3-2).

스트리밍 중 툴콜이 1급 시민 — 엔진별 파싱 편차는 각 어댑터가 흡수하고, 상위(Orchestrator)는
ChatDelta 스트림만 소비한다. reasoning(thinking) 토큰은 TTS/자막으로 내보내면 안 되므로
별도 델타 타입으로 분리한다.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from app.config import Settings


@dataclass
class ToolCall:
    """assistant 메시지에 실리는 완성된 툴 호출."""

    id: str
    name: str
    arguments: str  # JSON 문자열


@dataclass
class Message:
    """provider 무관 대화 메시지. role: system | user | assistant | tool."""

    role: str
    content: str = ""
    tool_calls: list[ToolCall] | None = None  # assistant 전용
    tool_call_id: str | None = None  # tool 전용 — 결과가 어느 호출의 것인지 (§7-3)


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class GenOptions:
    max_tokens: int = 1024
    request_id: str | None = None  # 바지-인 취소 대상 식별 (§4)


@dataclass
class TextDelta:
    text: str


@dataclass
class ReasoningDelta:
    """thinking 토큰 — 자막·TTS 금지 채널 (§7-3)."""

    text: str


@dataclass
class ToolCallDelta:
    """툴콜 조각. arguments는 누적 대상 부분 문자열."""

    index: int
    id: str | None = None
    name: str | None = None
    arguments: str = ""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Done:
    finish_reason: str  # stop | tool_calls | length | error
    usage: Usage = field(default_factory=Usage)


ChatDelta = TextDelta | ReasoningDelta | ToolCallDelta | Done


@dataclass
class LLMCapabilities:
    tools: bool = True
    json_schema: bool = False
    vision: bool = False
    reasoning: bool = False


@dataclass
class ProviderHealth:
    ok: bool
    detail: str = ""


class LLMProvider(ABC):
    """LLM 어댑터 계약. 구현체는 llm_registry에 등록한다 (§3-2)."""

    name: ClassVar[str] = ""

    @classmethod
    def from_settings(cls, settings: "Settings") -> "LLMProvider":
        """설정에서 인스턴스를 조립한다. 자격증명 누락 시 ProviderNotConfiguredError."""
        raise NotImplementedError

    @abstractmethod
    def chat_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSchema] | None = None,
        options: GenOptions | None = None,
    ) -> AsyncIterator[ChatDelta]:
        """대화를 스트리밍 생성한다. 마지막 델타는 반드시 Done."""

    @abstractmethod
    async def health(self) -> ProviderHealth:
        """LLMRouter의 가용성 판단용 (§7-5)."""

    @abstractmethod
    def capabilities(self) -> LLMCapabilities: ...

    @abstractmethod
    async def cancel(self, request_id: str) -> None:
        """진행 중인 요청을 즉시 중단한다 — 바지-인의 전제 (§4)."""
