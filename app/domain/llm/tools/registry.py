"""Tool Calling registry."""

from typing import Any, Callable, Coroutine

from loguru import logger

ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


class ToolRegistry:
    """LLM Tool Calling registry."""

    _tools: dict[str, dict[str, Any]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        *,
        description: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> Callable[[ToolFunc], ToolFunc]:
        """Tool registration decorator."""

        def decorator(func: ToolFunc) -> ToolFunc:
            cls._tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters or {},
                "handler": func,
            }
            logger.debug(f"Tool registered: {name}")
            return func

        return decorator

    @classmethod
    def get_tool(cls, name: str) -> dict[str, Any] | None:
        """Get tool by name."""
        return cls._tools.get(name)

    @classmethod
    async def execute(cls, name: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a tool."""
        tool = cls._tools.get(name)
        if not tool:
            return {"error": f"Tool not found: {name}"}

        handler = tool["handler"]
        logger.info(f"Tool executed: {name}, args={kwargs}")
        return await handler(**kwargs)

    @classmethod
    def get_tools_schema(cls) -> list[dict[str, Any]]:
        """Get tool schema list for LLM."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for tool in cls._tools.values()
        ]
