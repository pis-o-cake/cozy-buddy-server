"""Information query tools (Tool Calling)."""

from typing import Any

from app.core.i18n import t
from app.domain.llm.tools.registry import ToolRegistry


@ToolRegistry.register(
    "get_weather",
    description="현재 날씨 정보를 조회합니다",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "위치 (기본: 현재 위치)"},
        },
    },
)
async def get_weather(location: str = "") -> dict[str, Any]:
    """Weather query tool."""
    # TODO: Integrate weather API
    return {"location": location or "서울", "status": "pending"}


@ToolRegistry.register(
    "search_knowledge",
    description="저장된 문서/지식에서 관련 정보를 검색합니다. 사용자가 특정 정보를 물어보거나 기억해달라고 한 내용을 찾을 때 사용합니다.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색할 내용",
            },
            "top_k": {
                "type": "integer",
                "description": "검색 결과 수 (기본: 5)",
            },
        },
        "required": ["query"],
    },
)
async def search_knowledge(query: str, top_k: int = 5) -> dict[str, Any]:
    """RAG search tool."""
    from app.main import rag_service

    result = await rag_service.query(query=query, top_k=top_k)
    if not result.results:
        return {"found": False, "message": t("tool.search_no_results")}

    return {
        "found": True,
        "results": [
            {
                "content": r.content,
                "source": r.source,
                "score": r.score,
            }
            for r in result.results
        ],
    }
