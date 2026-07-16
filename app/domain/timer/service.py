"""timer 도메인 서비스 — 타이머/알람/리마인더 (설계서 §2-4·§9).

발화 시 대상 허브로 `timer.fired`(§5-1)를 push하고, 일회성은 행을 정리한다.
"""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.exceptions import NotFoundError
from app.core.scheduler import scheduler
from app.core.websocket import hub_manager
from app.domain.auth.models import Hub
from app.domain.timer import crud
from app.domain.timer.models import Timer

_VALID_KINDS = {"timer", "alarm", "reminder"}  # §5-1 timer.fired kind


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def parse_fires_at(*, duration_sec: int | None, at: str | None) -> datetime:
    """duration_sec(타이머) 또는 at("HH:MM"|ISO8601, 알람/리마인더) → 발화 시각."""
    if duration_sec is not None:
        return _now() + timedelta(seconds=int(duration_sec))
    if not at:
        raise ValueError("either duration_sec or at is required")
    if ":" in at and len(at) <= 5:  # "HH:MM" → 다음 도래 시각
        hour, minute = (int(part) for part in at.split(":"))
        candidate = _now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= _now():
            candidate += timedelta(days=1)
        return candidate
    return datetime.fromisoformat(at).replace(tzinfo=None)


async def create_timer(
    session: AsyncSession,
    *,
    hub_pk: int,
    kind: str,
    fires_at: datetime,
    label: str | None = None,
    recurrence: dict | None = None,
    sunrise: bool = False,
) -> Timer:
    if kind not in _VALID_KINDS:
        raise ValueError(f"invalid timer kind: {kind}")
    timer = await crud.create_timer(
        session,
        hub_id=hub_pk,
        kind=kind,
        label=label,
        fires_at=fires_at,
        recurrence=recurrence,
        sunrise=sunrise,
    )
    _schedule(timer)
    logger.info("timer created: #{} {} at {}", timer.id, kind, fires_at)
    return timer


async def cancel_timer(
    session: AsyncSession, *, hub_pk: int, timer_id: int | None = None, label: str | None = None
) -> Timer:
    timer = None
    if timer_id is not None:
        timer = await crud.get_timer(session, timer_id)
    elif label:
        timer = await crud.get_by_label(session, hub_pk, label)
    if timer is None:
        raise NotFoundError("timer not found")
    _unschedule(timer.id)
    await crud.delete_timer(session, timer)
    return timer


async def reschedule_all() -> None:
    """앱 기동 시 DB의 타이머를 잡으로 복원 — 재시작 내구성 (§9-2)."""
    async with get_session_factory()() as session:
        for timer in await crud.list_timers(session):
            if timer.recurrence is None and timer.fires_at <= _now():
                await crud.delete_timer(session, timer)  # 이미 지난 일회성 정리
                continue
            _schedule(timer)


def _schedule(timer: Timer) -> None:
    job_id = f"timer-{timer.id}"
    if timer.recurrence and timer.recurrence.get("cron"):
        trigger = CronTrigger.from_crontab(timer.recurrence["cron"], timezone="Asia/Seoul")
    else:
        trigger = DateTrigger(run_date=timer.fires_at)
    scheduler.add_job(_fire, trigger, args=[timer.id], id=job_id, replace_existing=True)


def _unschedule(timer_id: int) -> None:
    job = scheduler.get_job(f"timer-{timer_id}")
    if job is not None:
        job.remove()


async def _fire(timer_id: int) -> None:
    """발화: 대상 허브에 timer.fired push (§5-1) — 알람음/선라이즈 연출은 허브 담당."""
    async with get_session_factory()() as session:
        timer = await crud.get_timer(session, timer_id)
        if timer is None:
            return
        hub = await session.scalar(sa.select(Hub).where(Hub.id == timer.hub_id))
        payload = {
            "type": "timer.fired",
            "timer_id": timer.id,
            "label": timer.label,
            "kind": timer.kind,
            "sunrise": timer.sunrise,
        }
        delivered = hub is not None and await hub_manager.send_to(hub.hub_id, payload)
        if not delivered:
            logger.warning("timer #{} fired but hub not connected", timer.id)
        if timer.recurrence is None:
            await crud.delete_timer(session, timer)
