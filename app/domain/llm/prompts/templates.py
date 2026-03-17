"""Prompt templates."""

from app.core.i18n import t


def format_tool_result(*, tool_name: str, result: str) -> str:
    """Format tool result for LLM."""
    return t("prompt.tool_result", tool_name=tool_name, result=result)
