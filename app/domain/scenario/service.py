"""scenario 실행 엔진 + 스케줄러 연동 (설계서 §9).

- 액션은 order 순 직렬, 동일 parallel_group은 병렬 (§9-2).
- 부분 실패 정책(§12-1): 성공분 진행 + 실패 목록 보고 + scenario.executed push.
- 기기 참조는 device_id FK가 정본 (§9-2).
"""

import asyncio
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.scheduler import scheduler
from app.core.websocket import hub_manager
from app.domain.device import service as device_service
from app.domain.device.adapters.base import DeviceCommand
from app.domain.device.models import Device
from app.domain.scenario import crud
from app.domain.scenario.models import Scenario, ScenarioAction
from app.domain.scenario.schemas import ActionResult, RunResult


async def execute_scenario(session: AsyncSession, scenario: Scenario) -> RunResult:
    """액션을 실행한다.

    IMPORTANT: AsyncSession은 동시 사용 불가 — DB 접근(기기 로드·online 갱신)은 그룹
    전후로 직렬 수행하고, 병렬 구간에는 어댑터 I/O만 둔다 (§9-2 병렬 규약).
    """
    actions = await crud.get_actions(session, scenario.id)
    results: list[ActionResult] = []

    for group in _group_actions(actions):
        # 준비(직렬): device_command 대상 기기를 미리 로드
        runners = []
        loaded_devices: list[Device | None] = []
        for action in group:
            command: dict[str, Any] = action.command or {}
            device: Device | None = None
            if command.get("type") == "device_command" and action.device_id is not None:
                device = await session.get(Device, action.device_id)
            loaded_devices.append(device)
            runners.append(_run_action(action, command, device))

        # 실행: 동일 parallel_group은 동시 (§9-2)
        if len(runners) == 1:
            outcomes = [await runners[0]]
        else:
            outcomes = list(await asyncio.gather(*runners))

        # 정리(직렬): online 플래그 반영 (§12-1)
        dirty = False
        for device, outcome in zip(loaded_devices, outcomes, strict=True):
            if device is not None:
                device.online = outcome.ok
                dirty = True
            results.append(outcome)
        if dirty:
            await session.commit()

    run = RunResult(
        scenario_id=scenario.id, results=results, ok=all(r.ok for r in results)
    )
    await hub_manager.broadcast_all(
        {
            "type": "scenario.executed",
            "scenario_id": scenario.id,
            "results": [r.model_dump() for r in results],
        }
    )
    logger.info("scenario '{}' executed (ok={})", scenario.name, run.ok)
    return run


def _group_actions(actions: list[ScenarioAction]) -> list[list[ScenarioAction]]:
    """order 순 유지하며 연속된 동일 parallel_group을 묶는다."""
    groups: list[list[ScenarioAction]] = []
    for action in actions:
        if (
            groups
            and action.parallel_group is not None
            and groups[-1][0].parallel_group == action.parallel_group
        ):
            groups[-1].append(action)
        else:
            groups.append([action])
    return groups


async def _run_action(
    action: ScenarioAction, command: dict[str, Any], device: Device | None
) -> ActionResult:
    """단일 액션 실행 — DB 접근 없음(병렬 안전). 기기는 호출측이 미리 로드해 전달."""
    try:
        match command.get("type"):
            case "device_command":
                if device is None:
                    return ActionResult(order=action.order, ok=False, detail="device not found")
                result = await device_service.execute_with_retry(
                    device,
                    DeviceCommand(capability=command["capability"], value=command["value"]),
                )
                return ActionResult(order=action.order, ok=result.ok, detail=result.detail)
            case "wait":
                await asyncio.sleep(float(command.get("sec", 0)))
                return ActionResult(order=action.order, ok=True)
            case "tts_announce":
                return await _run_announce(command, action.order)
            case unknown:
                return ActionResult(
                    order=action.order, ok=False, detail=f"unknown action type: {unknown}"
                )
    except Exception as exc:  # 액션 실패는 시나리오 전체를 멈추지 않는다 (§12-1)
        logger.warning("scenario action {} failed: {}", action.order, exc)
        return ActionResult(order=action.order, ok=False, detail=str(exc))


async def _run_announce(command: dict[str, Any], order: int) -> ActionResult:
    # 순환 import 방지 — voice는 scenario를 모르고, scenario가 voice 헬퍼를 지연 참조
    from app.domain.voice.service import announce

    hub_id = str(command.get("hub", ""))
    text = str(command.get("text", ""))
    if not hub_id or not text:
        return ActionResult(order=order, ok=False, detail="hub or text missing")
    delivered = await announce(hub_id, text)
    return ActionResult(order=order, ok=delivered, detail="" if delivered else "hub not connected")


# ── 스케줄러 연동 (§9-1 트리거) ───────────────────────────────


async def _run_scheduled(scenario_id: int) -> None:
    async with get_session_factory()() as session:
        scenario = await crud.get_scenario(session, scenario_id)
        if scenario is None or not scenario.enabled:
            return
        await execute_scenario(session, scenario)


def sync_schedule(scenario: Scenario) -> None:
    """시나리오의 schedule 트리거를 APScheduler 잡으로 반영한다 (생성/수정 시 호출)."""
    job_id = f"scenario-{scenario.id}"
    existing = scheduler.get_job(job_id)
    if existing is not None:
        existing.remove()
    if not scenario.enabled:
        return
    for trigger in scenario.triggers or []:
        if trigger.get("type") == "schedule" and trigger.get("cron"):
            scheduler.add_job(
                _run_scheduled,
                CronTrigger.from_crontab(trigger["cron"], timezone="Asia/Seoul"),
                args=[scenario.id],
                id=job_id,
                replace_existing=True,
            )
            logger.info("scenario '{}' scheduled: {}", scenario.name, trigger["cron"])


async def sync_all_schedules() -> None:
    """앱 기동 시 enabled 시나리오 잡 일괄 등록 — 재시작 내구성 (§9-2)."""
    async with get_session_factory()() as session:
        for scenario in await crud.list_scenarios(session):
            sync_schedule(scenario)


async def enabled_names(session: AsyncSession) -> list[str]:
    """system prompt 힌트용 시나리오 이름 목록 (§9-1 voice 트리거)."""
    return [s.name for s in await crud.list_scenarios(session) if s.enabled]
