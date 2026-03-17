"""LLM domain API router."""

from fastapi import APIRouter

from app.domain.llm.schemas import LLMRequest, LLMResponse
from app.domain.llm.tools.registry import ToolRegistry

router = APIRouter()


@router.post("/chat", response_model=LLMResponse)
async def llm_chat(request: LLMRequest) -> LLMResponse:
    """Direct LLM chat without conversation context."""
    from app.main import llm_service

    tools_schema = ToolRegistry.get_tools_schema()
    tools = [{"type": "function", "function": t} for t in tools_schema] if tools_schema else None

    return await llm_service.chat(
        messages=request.messages,
        tools=request.tools or tools,
        provider=request.provider,
    )


@router.get("/providers")
async def list_providers() -> dict[str, list[str]]:
    """List available LLM providers."""
    from app.main import llm_service

    return {"providers": llm_service.get_available_providers()}
