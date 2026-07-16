"""timer 도메인 스키마 (설계서 §5-2)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TimerCreate(BaseModel):
    hub_id: str  # 울릴 허브 (문자열 식별자 — "living-01")
    kind: str  # timer | alarm | reminder
    duration_sec: int | None = None
    at: str | None = None  # "HH:MM" 또는 ISO8601
    label: str | None = None
    recurrence: dict[str, Any] | None = None  # {"cron": "0 7 * * 1-5"}
    sunrise: bool = False


class TimerOut(BaseModel):
    id: int
    hub_id: int
    kind: str
    label: str | None
    fires_at: datetime
    recurrence: dict[str, Any] | None
    sunrise: bool

    model_config = {"from_attributes": True}
