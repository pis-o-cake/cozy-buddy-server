"""Chat domain service."""

import json
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat import crud
from app.domain.chat.models import Conversation
from app.domain.llm.prompts.system import build_system_prompt
from app.domain.llm.prompts.templates import format_tool_result
from app.domain.llm.tools.registry import ToolRegistry

MAX_TOOL_ITERATIONS = 5


class ChatService:
    """Chat processing service."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_message(
        self,
        *,
        role: str,
        content: str,
        tool_call: dict[str, Any] | None = None,
    ) -> Conversation:
        """Save a message."""
        message = await crud.create_message(
            self._db, role=role, content=content, tool_call=tool_call
        )
        logger.debug(f"Message saved: role={role}, content={content[:50]}")
        return message

    async def get_context(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent conversation context for LLM."""
        messages = await crud.get_recent_messages(self._db, limit=limit)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                **({"tool_call": msg.tool_call} if msg.tool_call else {}),
            }
            for msg in messages
        ]

    async def process_message(
        self,
        *,
        content: str,
        provider: str | None = None,
    ) -> Conversation:
        """Process user message: save → LLM call → tool calling loop → save response."""
        from app.main import llm_service

        await self.save_message(role="user", content=content)

        context = await self.get_context()
        system_prompt = build_system_prompt(
            tools_description=self._format_tools_description(),
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *context,
        ]

        tools_schema = ToolRegistry.get_tools_schema()
        tools = [{"type": "function", "function": t} for t in tools_schema] if tools_schema else None

        # --- LLM call + Tool Calling loop ---
        response = await llm_service.chat(
            messages=messages, tools=tools, provider=provider
        )

        for _ in range(MAX_TOOL_ITERATIONS):
            if not response.tool_calls:
                break

            tool_results = await self._execute_tool_calls(response.tool_calls)

            messages.append({"role": "assistant", "content": response.content or ""})
            for tc, result in zip(response.tool_calls, tool_results):
                messages.append({
                    "role": "user",
                    "content": format_tool_result(
                        tool_name=tc["function"]["name"],
                        result=json.dumps(result, ensure_ascii=False),
                    ),
                })

            response = await llm_service.chat(
                messages=messages, tools=tools, provider=provider
            )

        assistant_msg = await self.save_message(
            role="assistant",
            content=response.content,
            tool_call=response.tool_calls,
        )
        return assistant_msg

    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []
        for tc in tool_calls:
            func_info = tc.get("function", {})
            name = func_info.get("name", "")
            args_str = func_info.get("arguments", "{}")

            try:
                kwargs = json.loads(args_str)
            except json.JSONDecodeError:
                kwargs = {}

            result = await ToolRegistry.execute(name, **kwargs)
            results.append(result)

            await self.save_message(
                role="assistant",
                content=f"[tool_call] {name}",
                tool_call={"name": name, "args": kwargs, "result": result},
            )
        return results

    @staticmethod
    def _format_tools_description() -> str:
        """Format registered tools for system prompt."""
        tools = ToolRegistry.get_tools_schema()
        if not tools:
            return ""
        return "\n".join(f"- {t['name']}: {t['description']}" for t in tools)

    async def process_message_stream(
        self,
        *,
        content: str,
        provider: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Process user message with streaming LLM response.

        Tool calls are handled non-streaming first, then final response is streamed.
        """
        from app.main import llm_service

        await self.save_message(role="user", content=content)

        context = await self.get_context()
        system_prompt = build_system_prompt(
            tools_description=self._format_tools_description(),
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *context,
        ]

        tools_schema = ToolRegistry.get_tools_schema()
        tools = [{"type": "function", "function": t} for t in tools_schema] if tools_schema else None

        # --- Tool Calling loop (non-streaming) ---
        response = await llm_service.chat(
            messages=messages, tools=tools, provider=provider
        )

        for _ in range(MAX_TOOL_ITERATIONS):
            if not response.tool_calls:
                break

            tool_results = await self._execute_tool_calls(response.tool_calls)

            messages.append({"role": "assistant", "content": response.content or ""})
            for tc, result in zip(response.tool_calls, tool_results):
                messages.append({
                    "role": "user",
                    "content": format_tool_result(
                        tool_name=tc["function"]["name"],
                        result=json.dumps(result, ensure_ascii=False),
                    ),
                })

            response = await llm_service.chat(
                messages=messages, tools=tools, provider=provider
            )

        # --- Final response: stream if no tool calls remain ---
        if not response.tool_calls:
            full_content = ""
            async for chunk in llm_service.chat_stream(
                messages=messages, provider=provider
            ):
                full_content += chunk
                yield chunk

            await self.save_message(role="assistant", content=full_content)
        else:
            await self.save_message(
                role="assistant",
                content=response.content,
                tool_call=response.tool_calls,
            )
            yield response.content
