"""System prompt definition."""

from app.core.i18n import t


def build_system_prompt(
    *,
    tools_description: str = "",
    devices_description: str = "",
) -> str:
    """Build system prompt."""
    return t(
        "prompt.system",
        tools_description=tools_description or t("prompt.none"),
        devices_description=devices_description or t("prompt.none"),
    )
