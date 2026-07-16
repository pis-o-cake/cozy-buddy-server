"""테스트용 fake provider — 레지스트리에 "fake" 이름으로 등록된다."""

import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar

from app.config import Settings
from app.domain.device.adapters.base import (
    CommandResult,
    DeviceAdapter,
    DeviceCommand,
    DeviceState,
    DiscoveredDevice,
    adapter_registry,
)
from app.domain.device.models import Device
from app.domain.llm.providers.base import (
    ChatDelta,
    Done,
    GenOptions,
    LLMCapabilities,
    LLMProvider,
    Message,
    ProviderHealth,
    TextDelta,
    ToolSchema,
)
from app.domain.llm.providers.registry import llm_registry
from app.domain.voice.factory import stt_registry, tts_registry
from app.domain.voice.providers.stt_base import STTProvider, STTResult
from app.domain.voice.providers.tts_base import AudioChunk, TTSCapabilities, TTSProvider


@llm_registry.register("fake")
class FakeLLM(LLMProvider):
    name: ClassVar[str] = "fake"

    def __init__(
        self,
        scripts: list[list[ChatDelta]] | None = None,
        *,
        first_delta_delay: float = 0.0,
    ) -> None:
        default_script: list[ChatDelta] = [
            TextDelta(text="거실 조명을 껐어요."),
            Done(finish_reason="stop"),
        ]
        self._scripts = scripts or [default_script]
        self._call_count = 0
        self._first_delta_delay = first_delta_delay
        self.cancelled: list[str] = []
        self.received: list[list[Message]] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> "FakeLLM":
        return cls()

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSchema] | None = None,
        options: GenOptions | None = None,
    ) -> AsyncIterator[ChatDelta]:
        self.received.append(list(messages))
        if self._first_delta_delay:
            await asyncio.sleep(self._first_delta_delay)
        script = self._scripts[min(self._call_count, len(self._scripts) - 1)]
        self._call_count += 1
        for delta in script:
            yield delta

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True)

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities()

    async def cancel(self, request_id: str) -> None:
        self.cancelled.append(request_id)


@stt_registry.register("fake")
class FakeSTT(STTProvider):
    name: ClassVar[str] = "fake"
    next_result: ClassVar[STTResult] = STTResult(text="불 꺼줘", confidence=0.95, duration_ms=12)

    def __init__(self, settings: Settings | None = None) -> None:
        pass

    async def initialize(self) -> None:
        pass

    async def transcribe(
        self,
        pcm: bytes,
        *,
        rate: int = 16000,
        lang: str = "ko",
        initial_prompt: str | None = None,
    ) -> STTResult:
        return type(self).next_result

    async def shutdown(self) -> None:
        pass


@adapter_registry.register("fakeadp")
class FakeDeviceAdapter(DeviceAdapter):
    """execute 결과를 기록하고, fail_times만큼 실패를 시뮬레이션한다."""

    adapter_type: ClassVar[str] = "fakeadp"
    fail_times: ClassVar[int] = 0
    executed: ClassVar[list[tuple[str, str, object]]] = []

    @classmethod
    def reset(cls) -> None:
        cls.fail_times = 0
        cls.executed = []

    async def discover(self) -> list[DiscoveredDevice]:
        return [
            DiscoveredDevice(
                adapter_type="fakeadp",
                name="발견된 플러그",
                model="FAKE-1",
                config={"host": "10.0.0.9"},
                suggested_type="plug",
            )
        ]

    async def identify(self, device: Device) -> None:
        type(self).executed.append((device.name, "identify", None))

    async def get_state(self, device: Device) -> DeviceState:
        return DeviceState(online=True, attributes={"on_off": "on"})

    async def execute(self, device: Device, command: DeviceCommand) -> CommandResult:
        cls = type(self)
        cls.executed.append((device.name, command.capability, command.value))
        if cls.fail_times > 0:
            cls.fail_times -= 1
            return CommandResult(ok=False, detail="simulated failure")
        return CommandResult(ok=True)


@tts_registry.register("fake")
class FakeTTS(TTSProvider):
    name: ClassVar[str] = "fake"

    def __init__(self, settings: Settings | None = None) -> None:
        pass

    async def initialize(self) -> None:
        pass

    async def synthesize_stream(
        self, text: str, *, voice: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        yield AudioChunk(pcm=b"\x01\x02" * 80, rate=16000, is_last=True)

    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(streaming=False)

    async def shutdown(self) -> None:
        pass
