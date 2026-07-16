"""음성 세션 핸들러 — 발화 1회의 전체 파이프라인 (설계서 §4).

허브 연결당 1개. WS 수신 루프(ws.py)와 파이프라인(별도 task)을 분리해
tts.cancel(바지-인) 같은 제어 메시지가 파이프라인 실행 중에도 처리되게 한다.
"""

import asyncio
import json
import uuid
from typing import Any

from fastapi import WebSocket
from loguru import logger

from app.config import get_settings
from app.core.database import get_session_factory
from app.core.i18n import t
from app.core.websocket import hub_manager
from app.domain.chat import service as chat_service
from app.domain.device import service as device_service
from app.domain.llm.providers.base import Message
from app.domain.llm.service import (
    HubContext,
    OrchDone,
    Orchestrator,
    OrchTextDelta,
    OrchToolStatus,
)
from app.domain.scenario import service as scenario_service
from app.domain.voice import runtime
from app.domain.voice.sentence import SentenceSplitter

UPLINK_AUDIO_TAG = 0x01  # 허브→서버 마이크 PCM (§5-1)
DOWNLINK_TTS_TAG = 0x02  # 서버→허브 TTS PCM (§5-1)
_MAX_UTTERANCE_BYTES = 16000 * 2 * 20  # 16kHz PCM16 20초 상한 (§4 maxUtteranceMs 방어)


async def announce(hub_id: str, text: str) -> bool:
    """서버 발신 방송 (§5-1 broadcast) — 시나리오 tts_announce·인터콤 공용.

    대상 허브에 broadcast 메시지 + TTS 오디오(0x02)를 push한다. 미연결이면 False.
    """
    websocket = hub_manager.get(hub_id)
    if websocket is None:
        return False
    await hub_manager.send_to(hub_id, {"type": "broadcast", "from_hub": "server", "text": text})
    try:
        tts = await runtime.get_tts()
        started = False
        async for chunk in tts.synthesize_stream(text):
            if not started:
                start_msg = {
                    "type": "tts.start",
                    "session_id": "",
                    "codec": "pcm16",
                    "rate": chunk.rate,
                }
                await hub_manager.send_to(hub_id, start_msg)
                started = True
            await websocket.send_bytes(bytes([DOWNLINK_TTS_TAG]) + chunk.pcm)
        if started:
            await hub_manager.send_to(hub_id, {"type": "tts.end", "session_id": ""})
    except Exception as exc:
        # 오디오 실패 시 텍스트 broadcast만으로 폴백 (§12-1)
        logger.warning("announce tts failed: {}", exc)
    return True


class VoiceSessionHandler:
    def __init__(self, websocket: WebSocket, *, hub_pk: int, hub_id: str, room: str | None) -> None:
        self._ws = websocket
        self._hub_pk = hub_pk
        self._hub = HubContext(hub_id=hub_id, room=room)
        self._audio = bytearray()
        self._collecting = False
        self._session_id: str = ""
        self._pipeline_task: asyncio.Task[None] | None = None
        self._cancel = asyncio.Event()
        self._request_id: str = ""

    # ── WS 수신 디스패치 ──────────────────────────────────────

    async def handle_text(self, raw: str) -> None:
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error("bad_message")
            return

        match data.get("type"):
            case "utterance.start":
                self._begin_utterance(data)
            case "utterance.end":
                await self._end_utterance()
            case "utterance.cancel":
                self._reset_utterance()
            case "text.query":
                await self._start_pipeline(text=str(data.get("text", "")))
            case "tts.cancel":
                await self._barge_in()
            case "ping":
                await self._send({"type": "pong", "ts": data.get("ts")})
            case other:
                logger.warning("unknown ws message type: {} (hub={})", other, self._hub.hub_id)

    async def handle_bytes(self, payload: bytes) -> None:
        if not payload or payload[0] != UPLINK_AUDIO_TAG or not self._collecting:
            return
        if len(self._audio) + len(payload) > _MAX_UTTERANCE_BYTES:
            logger.warning("utterance too long, dropping (hub={})", self._hub.hub_id)
            self._reset_utterance()
            await self._send_error("utterance_too_long")
            return
        self._audio.extend(payload[1:])

    async def close(self) -> None:
        if self._pipeline_task is not None:
            self._pipeline_task.cancel()

    # ── 발화 수집 ─────────────────────────────────────────────

    def _begin_utterance(self, data: dict[str, Any]) -> None:
        self._audio.clear()
        self._collecting = True
        self._session_id = str(data.get("session_id", ""))

    def _reset_utterance(self) -> None:
        self._audio.clear()
        self._collecting = False

    async def _end_utterance(self) -> None:
        if not self._collecting:
            return
        self._collecting = False
        pcm = bytes(self._audio)
        self._audio.clear()
        await self._start_pipeline(pcm=pcm)

    # ── 파이프라인 ────────────────────────────────────────────

    async def _start_pipeline(self, *, pcm: bytes | None = None, text: str | None = None) -> None:
        if self._pipeline_task is not None and not self._pipeline_task.done():
            # 단일 허브 직렬 처리(§8): 진행 중 턴은 새 발화가 대체한다
            await self._barge_in()
            self._pipeline_task.cancel()
        self._cancel = asyncio.Event()
        self._request_id = uuid.uuid4().hex
        self._pipeline_task = asyncio.create_task(self._run_pipeline(pcm=pcm, text=text))

    async def _barge_in(self) -> None:
        """SPEAKING 중단 — TTS 스트림 중지 + LLM 요청 취소 (§4 바지-인)."""
        self._cancel.set()
        try:
            await runtime.get_llm().cancel(self._request_id)
        except Exception as exc:
            logger.warning("llm cancel failed: {}", exc)

    async def _run_pipeline(self, *, pcm: bytes | None, text: str | None) -> None:
        settings = get_settings()
        try:
            # 1) STT (음성 입력일 때만 — text.query는 우회)
            if text is None:
                stt = await runtime.get_stt()
                result = await stt.transcribe(pcm or b"", rate=16000, lang="ko")
                if not result.text or result.confidence < settings.stt_confidence_threshold:
                    # 저신뢰/공백은 error가 아닌 정상 되묻기 경로 (§12-1)
                    await self._respond_fixed(t("voice.repeat_please"))
                    return
                text = result.text
                await self._send(
                    {
                        "type": "stt.final",
                        "session_id": self._session_id,
                        "text": text,
                        "confidence": round(result.confidence, 3),
                    }
                )
            await self._send({"type": "state", "value": "thinking"})

            # 2) 세션 컨텍스트(§7-4) + 기기/시나리오 프롬프트 블록(§7-1 블록4 — 매 턴 DB에서
            #    새로 조립하므로 등록 즉시 반영, §8-2)
            session_factory = get_session_factory()
            async with session_factory() as db:
                chat_session = await chat_service.get_or_create_session(db, self._hub_pk)
                history, summary = await chat_service.load_context(db, chat_session)
                devices_block = await device_service.prompt_block(db)
                scenario_names = await scenario_service.enabled_names(db)
            if scenario_names:
                prefix = devices_block or t("prompt.no_devices")
                names = ", ".join(scenario_names)
                devices_block = f"{prefix}\n{t('prompt.scenarios_prefix')}: {names}"

            # 3) LLM tool loop + 문장 단위 TTS (§4 · §7-3)
            llm = runtime.get_llm()
            orchestrator = Orchestrator(llm)
            user_message = Message(role="user", content=text)
            splitter = SentenceSplitter()
            tts_started = False
            done: OrchDone | None = None

            async for event in orchestrator.run_turn(
                [*history, user_message],
                self._hub,
                summary=summary,
                devices_block=devices_block,
                request_id=self._request_id,
            ):
                if self._cancel.is_set():
                    break
                match event:
                    case OrchTextDelta(text=delta_text):
                        delta_msg = {
                            "type": "llm.delta",
                            "session_id": self._session_id,
                            "text": delta_text,
                        }
                        await self._send(delta_msg)
                        for sentence in splitter.feed(delta_text):
                            tts_started = await self._speak(sentence, tts_started)
                    case OrchToolStatus(tool=tool, status=status):
                        await self._send({"type": "tool.status", "tool": tool, "status": status})
                    case OrchDone() as d:
                        done = d

            if self._cancel.is_set() or done is None:
                await self._send({"type": "state", "value": "idle"})
                return

            remainder = splitter.flush()
            if remainder:
                tts_started = await self._speak(remainder, tts_started)
            # 스트리밍된 문장이 하나도 없으면(툴 루프 초과 등 고정 응답) 전문을 합성
            if not tts_started and done.text:
                tts_started = await self._speak(done.text, tts_started)
            if tts_started:
                await self._send({"type": "tts.end", "session_id": self._session_id})
            await self._send(
                {"type": "response", "session_id": self._session_id, "text": done.text}
            )

            # 4) 세션 저장 + 롤링 요약 (응답 이후 — 체감 지연 무관, §7-4)
            async with session_factory() as db:
                chat_session = await chat_service.get_or_create_session(db, self._hub_pk)
                await chat_service.append_messages(
                    db, chat_session, [user_message, *done.new_messages]
                )
                await chat_service.maybe_roll_summary(db, chat_session, llm)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("voice pipeline failed (hub={})", self._hub.hub_id)
            await self._send_error("pipeline_failed", message_key="voice.pipeline_failed")
        finally:
            await self._send({"type": "state", "value": "idle"})

    async def _respond_fixed(self, message: str) -> None:
        """되묻기 등 고정 문구 응답 — 정상 response + TTS 경로 (§12-1)."""
        tts_started = await self._speak(message, False)
        if tts_started:
            await self._send({"type": "tts.end", "session_id": self._session_id})
        await self._send({"type": "response", "session_id": self._session_id, "text": message})

    async def _speak(self, sentence: str, tts_started: bool) -> bool:
        """문장 하나를 합성해 0x02 바이너리로 스트리밍한다. Returns: tts.start 송신 여부."""
        try:
            tts = await runtime.get_tts()
            async for chunk in tts.synthesize_stream(sentence):
                if self._cancel.is_set():
                    return tts_started
                if not tts_started:
                    await self._send(
                        {
                            "type": "tts.start",
                            "session_id": self._session_id,
                            "codec": "pcm16",
                            "rate": chunk.rate,
                        }
                    )
                    tts_started = True
                await self._ws.send_bytes(bytes([DOWNLINK_TTS_TAG]) + chunk.pcm)
            return tts_started
        except Exception as exc:
            # TTS 실패 시 무음 + 자막(response)으로 폴백 — 무응답 방지 (§12-1)
            logger.warning("tts failed, falling back to text only: {}", exc)
            return tts_started

    async def _send(self, payload: dict[str, Any]) -> None:
        await self._ws.send_json(payload)

    async def _send_error(self, code: str, *, message_key: str = "errors.internal") -> None:
        await self._send(
            {
                "type": "error",
                "code": code,
                "message": t(message_key),
                "session_id": self._session_id,
            }
        )
