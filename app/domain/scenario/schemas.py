"""scenario 도메인 스키마 (설계서 §9-2 — command는 액션 타입별 json)."""

from typing import Any

from pydantic import BaseModel, Field


class ActionIn(BaseModel):
    order: int
    parallel_group: int | None = None  # 동일 그룹 = 병렬 (§9-2)
    device_id: int | None = None  # device_command의 정본 참조 (§9-2)
    command: dict[str, Any]  # {type: device_command|tts_announce|wait|timer_set, ...}


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    triggers: list[dict[str, Any]] = Field(default_factory=list)  # §9-1
    enabled: bool = True
    actions: list[ActionIn] = Field(default_factory=list)


class ActionOut(ActionIn):
    id: int

    model_config = {"from_attributes": True}


class ScenarioOut(BaseModel):
    id: int
    name: str
    triggers: list[dict[str, Any]]
    enabled: bool

    model_config = {"from_attributes": True}


class ActionResult(BaseModel):
    order: int
    ok: bool
    detail: str = ""


class RunResult(BaseModel):
    scenario_id: int
    results: list[ActionResult]
    ok: bool  # 전체 성공 여부 (부분 실패 시 False — §12-1)
