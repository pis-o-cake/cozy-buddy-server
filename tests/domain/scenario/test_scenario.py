"""scenario 도메인 테스트."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ScenarioError
from app.domain.scenario import crud
from app.domain.scenario.schemas import ScenarioAction, ScenarioCreate
from app.domain.scenario.service import ScenarioService


class TestScenarioCRUD:
    """시나리오 CRUD 테스트."""

    @pytest.mark.asyncio
    async def test_create_scenario(self, db_session: AsyncSession):
        """시나리오 생성."""
        scenario = await crud.create_scenario(
            db_session,
            name="영화 모드",
            actions=[
                {"device_name": "거실 조명", "action": "set_brightness", "value": 10},
                {"device_name": "TV", "action": "on"},
            ],
            trigger="voice",
        )
        assert scenario.id is not None
        assert scenario.name == "영화 모드"
        assert len(scenario.actions) == 2
        assert scenario.trigger == "voice"

    @pytest.mark.asyncio
    async def test_get_scenario_by_name(self, db_session: AsyncSession):
        """이름으로 시나리오 조회."""
        await crud.create_scenario(
            db_session,
            name="취침 모드",
            actions=[{"device_name": "전체", "action": "off"}],
        )
        await db_session.flush()

        found = await crud.get_scenario_by_name(db_session, name="취침 모드")
        assert found is not None
        assert found.name == "취침 모드"

    @pytest.mark.asyncio
    async def test_get_scenario_not_found(self, db_session: AsyncSession):
        """존재하지 않는 시나리오."""
        found = await crud.get_scenario_by_name(db_session, name="없는 모드")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_all_scenarios(self, db_session: AsyncSession):
        """전체 시나리오 조회."""
        await crud.create_scenario(
            db_session, name="모드1", actions=[{"device_name": "a", "action": "on"}]
        )
        await crud.create_scenario(
            db_session, name="모드2", actions=[{"device_name": "b", "action": "off"}]
        )
        await db_session.flush()

        scenarios = await crud.get_all_scenarios(db_session)
        assert len(scenarios) == 2


class TestScenarioService:
    """시나리오 서비스 테스트."""

    @pytest.mark.asyncio
    async def test_create_scenario(self, db_session: AsyncSession):
        """시나리오 생성."""
        service = ScenarioService(db_session)
        scenario = await service.create_scenario(
            name="외출 모드",
            actions=[{"device_name": "전체", "action": "off"}],
            trigger="manual",
        )
        assert scenario.name == "외출 모드"

    @pytest.mark.asyncio
    async def test_activate_scenario_not_found(self, db_session: AsyncSession):
        """존재하지 않는 시나리오 실행."""
        service = ScenarioService(db_session)
        with pytest.raises(ScenarioError, match="not found"):
            await service.activate_scenario(name="없는 모드")

    @pytest.mark.asyncio
    async def test_activate_scenario_success(self, db_session: AsyncSession):
        """시나리오 실행 성공."""
        service = ScenarioService(db_session)
        await service.create_scenario(
            name="영화 모드",
            actions=[
                {"device_name": "조명", "action": "set_brightness", "value": 10},
            ],
        )
        await db_session.flush()

        result = await service.activate_scenario(name="영화 모드")
        assert result["status"] == "executed"
        assert result["actions_count"] == 1


class TestScenarioSchemas:
    """시나리오 스키마 테스트."""

    def test_scenario_action(self):
        """액션 스키마."""
        action = ScenarioAction(device_name="조명", action="on")
        assert action.value is None

    def test_scenario_create(self):
        """생성 요청 스키마."""
        req = ScenarioCreate(
            name="테스트",
            actions=[ScenarioAction(device_name="조명", action="on")],
        )
        assert req.trigger == "manual"
