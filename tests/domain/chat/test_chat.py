"""Chat domain tests."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat import crud
from app.domain.chat.models import Conversation
from app.domain.chat.service import ChatService
from app.domain.llm.schemas import LLMResponse


class TestChatCRUD:
    """대화 CRUD 테스트."""

    @pytest.mark.asyncio
    async def test_create_message(self, db_session: AsyncSession):
        """메시지 생성."""
        msg = await crud.create_message(
            db_session, role="user", content="안녕하세요"
        )
        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "안녕하세요"
        assert msg.tool_call is None

    @pytest.mark.asyncio
    async def test_create_message_with_tool_call(self, db_session: AsyncSession):
        """Tool Call 포함 메시지 생성."""
        tool_data = {"function": "turn_on", "args": {"device": "조명"}}
        msg = await crud.create_message(
            db_session, role="assistant", content="조명 켜기", tool_call=tool_data
        )
        assert msg.tool_call == tool_data

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, db_session: AsyncSession):
        """최근 메시지 조회."""
        for i in range(5):
            await crud.create_message(
                db_session, role="user", content=f"메시지 {i}"
            )
        await db_session.flush()

        messages = await crud.get_recent_messages(db_session, limit=3)
        assert len(messages) == 3
        contents = [m.content for m in messages]
        assert contents == ["메시지 2", "메시지 3", "메시지 4"]

    @pytest.mark.asyncio
    async def test_get_recent_messages_empty(self, db_session: AsyncSession):
        """메시지 없을 때 빈 목록."""
        messages = await crud.get_recent_messages(db_session)
        assert messages == []


class TestChatService:
    """대화 서비스 테스트."""

    @pytest.mark.asyncio
    async def test_save_message(self, db_session: AsyncSession):
        """메시지 저장."""
        service = ChatService(db_session)
        msg = await service.save_message(role="user", content="테스트")
        assert msg.role == "user"
        assert msg.content == "테스트"

    @pytest.mark.asyncio
    async def test_get_context(self, db_session: AsyncSession):
        """대화 컨텍스트 조회."""
        service = ChatService(db_session)
        await service.save_message(role="user", content="질문")
        await service.save_message(role="assistant", content="답변")
        await db_session.flush()

        context = await service.get_context(limit=10)
        assert len(context) == 2
        roles = [c["role"] for c in context]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_get_context_excludes_tool_call_when_none(self, db_session: AsyncSession):
        """tool_call이 None이면 컨텍스트에 미포함."""
        service = ChatService(db_session)
        await service.save_message(role="user", content="일반 메시지")
        await db_session.flush()

        context = await service.get_context()
        assert "tool_call" not in context[0]


class TestProcessMessage:
    """process_message integration tests."""

    @pytest.mark.asyncio
    async def test_simple_response(self, db_session: AsyncSession):
        """LLM returns text without tool calls."""
        service = ChatService(db_session)
        mock_response = LLMResponse(content="안녕하세요!", tool_calls=None)

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=mock_response)

        with patch("app.main.llm_service", mock_llm):
            result = await service.process_message(content="안녕")

        assert result.role == "assistant"
        assert result.content == "안녕하세요!"

        context = await service.get_context()
        roles = [c["role"] for c in context]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_with_tool_call(self, db_session: AsyncSession):
        """LLM calls a tool, then returns final response."""
        service = ChatService(db_session)

        tool_call_response = LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "서울"}),
                },
            }],
        )
        final_response = LLMResponse(content="서울 날씨는 맑습니다.", tool_calls=None)

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=[tool_call_response, final_response])

        with patch("app.main.llm_service", mock_llm):
            result = await service.process_message(content="날씨 알려줘")

        assert result.content == "서울 날씨는 맑습니다."
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_provider_forwarded(self, db_session: AsyncSession):
        """Provider parameter is forwarded to LLM service."""
        service = ChatService(db_session)
        mock_response = LLMResponse(content="OK", tool_calls=None)

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=mock_response)

        with patch("app.main.llm_service", mock_llm):
            await service.process_message(content="테스트", provider="openai")

        call_kwargs = mock_llm.chat.call_args
        assert call_kwargs.kwargs["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_max_tool_iterations(self, db_session: AsyncSession):
        """Tool calling loop respects MAX_TOOL_ITERATIONS."""
        service = ChatService(db_session)

        infinite_tool_response = LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_loop",
                "function": {
                    "name": "get_weather",
                    "arguments": "{}",
                },
            }],
        )

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=infinite_tool_response)

        with patch("app.main.llm_service", mock_llm):
            result = await service.process_message(content="무한루프")

        # MAX_TOOL_ITERATIONS(5) + initial call = 6
        assert mock_llm.chat.call_count == 6


class TestProcessMessageStream:
    """process_message_stream tests."""

    @pytest.mark.asyncio
    async def test_stream_simple_response(self, db_session: AsyncSession):
        """Streaming returns chunks and saves full content."""
        service = ChatService(db_session)

        no_tool_response = LLMResponse(content="", tool_calls=None)

        async def mock_stream(**kwargs):
            for chunk in ["안녕", "하세", "요!"]:
                yield chunk

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=no_tool_response)
        mock_llm.chat_stream = mock_stream

        chunks = []
        with patch("app.main.llm_service", mock_llm):
            async for chunk in service.process_message_stream(content="안녕"):
                chunks.append(chunk)

        assert chunks == ["안녕", "하세", "요!"]

        context = await service.get_context()
        assistant_msgs = [c for c in context if c["role"] == "assistant"]
        assert any(m["content"] == "안녕하세요!" for m in assistant_msgs)

    @pytest.mark.asyncio
    async def test_stream_with_tool_call_then_stream(self, db_session: AsyncSession):
        """Tool calls resolved non-streaming, final response streamed."""
        service = ChatService(db_session)

        tool_call_response = LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "서울"}),
                },
            }],
        )
        no_tool_response = LLMResponse(content="", tool_calls=None)

        async def mock_stream(**kwargs):
            for chunk in ["서울은 ", "맑음"]:
                yield chunk

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=[tool_call_response, no_tool_response])
        mock_llm.chat_stream = mock_stream

        chunks = []
        with patch("app.main.llm_service", mock_llm):
            async for chunk in service.process_message_stream(content="날씨"):
                chunks.append(chunk)

        assert chunks == ["서울은 ", "맑음"]
        assert mock_llm.chat.call_count == 2


class TestChatHistoryCRUD:
    """Chat history CRUD tests."""

    @pytest.mark.asyncio
    async def test_get_message_count(self, db_session: AsyncSession):
        """Message count returns correct value."""
        assert await crud.get_message_count(db_session) == 0

        await crud.create_message(db_session, role="user", content="msg1")
        await crud.create_message(db_session, role="assistant", content="msg2")
        await db_session.flush()

        assert await crud.get_message_count(db_session) == 2

    @pytest.mark.asyncio
    async def test_clear_messages(self, db_session: AsyncSession):
        """Clear deletes all messages and returns count."""
        for i in range(3):
            await crud.create_message(db_session, role="user", content=f"msg{i}")
        await db_session.flush()

        deleted = await crud.clear_messages(db_session)
        assert deleted == 3
        assert await crud.get_message_count(db_session) == 0

    @pytest.mark.asyncio
    async def test_clear_empty(self, db_session: AsyncSession):
        """Clear on empty table returns 0."""
        deleted = await crud.clear_messages(db_session)
        assert deleted == 0
