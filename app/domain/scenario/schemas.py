"""Scenario domain schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ScenarioAction(BaseModel):
    """Scenario individual action."""

    device_name: str
    action: str
    value: Any = None


class ScenarioCreate(BaseModel):
    """Scenario creation request."""

    name: str = Field(..., description="Scenario name")
    actions: list[ScenarioAction] = Field(..., description="Action list")
    trigger: str = Field(default="manual", description="Trigger type")


class ScenarioResponse(BaseModel):
    """Scenario response."""

    id: int
    name: str
    actions: list[dict[str, Any]]
    trigger: str

    model_config = {"from_attributes": True}
