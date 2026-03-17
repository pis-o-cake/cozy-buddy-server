"""llm 도메인 테스트."""

import pytest

from app.core.exceptions import LLMError
from app.domain.llm.prompts.system import build_system_prompt
from app.domain.llm.schemas import LLMRequest, LLMResponse
from app.domain.llm.service import LLMService
from app.domain.llm.tools.registry import ToolRegistry


class TestToolRegistry:
    """Tool Registry 테스트."""

    def setup_method(self):
        """각 테스트 전 레지스트리 초기화."""
        ToolRegistry._tools.clear()

    def test_register_tool(self):
        """도구 등록."""

        @ToolRegistry.register("test_tool", description="테스트 도구")
        async def test_func() -> dict:
            return {"ok": True}

        assert ToolRegistry.get_tool("test_tool") is not None
        assert ToolRegistry.get_tool("test_tool")["description"] == "테스트 도구"

    def test_get_tool_not_found(self):
        """미등록 도구 조회."""
        assert ToolRegistry.get_tool("없는_도구") is None

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """도구 실행."""

        @ToolRegistry.register("add", description="더하기")
        async def add_func(a: int = 0, b: int = 0) -> dict:
            return {"result": a + b}

        result = await ToolRegistry.execute("add", a=3, b=5)
        assert result["result"] == 8

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """미등록 도구 실행."""
        result = await ToolRegistry.execute("unknown")
        assert "error" in result

    def test_get_tools_schema(self):
        """도구 스키마 목록."""

        @ToolRegistry.register(
            "my_tool",
            description="내 도구",
            parameters={"type": "object", "properties": {}},
        )
        async def my_func() -> dict:
            return {}

        schemas = ToolRegistry.get_tools_schema()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "my_tool"
        assert "handler" not in schemas[0]


class TestSystemPrompt:
    """시스템 프롬프트 테스트."""

    def test_build_default_prompt(self):
        """기본 프롬프트 생성."""
        prompt = build_system_prompt()
        assert "코지버디" in prompt
        assert "없음" in prompt  # 도구/장치 미설정

    def test_build_prompt_with_tools(self):
        """도구 설명 포함 프롬프트."""
        prompt = build_system_prompt(
            tools_description="- control_device: 장치 제어",
            devices_description='- "거실 조명" (Tapo L530)',
        )
        assert "control_device" in prompt
        assert "거실 조명" in prompt


class TestLLMSchemas:
    """LLM 스키마 테스트."""

    def test_llm_request(self):
        """요청 스키마."""
        req = LLMRequest(
            messages=[{"role": "user", "content": "안녕"}],
            provider="vllm",
        )
        assert req.provider == "vllm"
        assert len(req.messages) == 1

    def test_llm_response(self):
        """응답 스키마."""
        resp = LLMResponse(content="안녕하세요!")
        assert resp.content == "안녕하세요!"
        assert resp.tool_calls is None

    def test_llm_response_with_tool_calls(self):
        """Tool Call 포함 응답."""
        resp = LLMResponse(
            content="",
            tool_calls=[{"id": "1", "function": {"name": "on", "arguments": "{}"}}],
        )
        assert len(resp.tool_calls) == 1


class TestLLMService:
    """LLM 서비스 테스트."""

    def test_get_adapter_before_init(self):
        """초기화 전 어댑터 접근."""
        service = LLMService()
        with pytest.raises(LLMError, match="unavailable"):
            service._get_adapter("vllm")

    def test_get_available_providers_empty(self):
        """초기화 전 프로바이더 목록."""
        service = LLMService()
        assert service.get_available_providers() == []
