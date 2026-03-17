"""device 도메인 테스트."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeviceError, DeviceOfflineError
from app.domain.device import crud
from app.domain.device.adapters.base import DeviceAdapter
from app.domain.device.adapters.tapo import TapoAdapter
from app.domain.device.service import DeviceService


class TestDeviceCRUD:
    """장치 CRUD 테스트."""

    @pytest.mark.asyncio
    async def test_create_device(self, db_session: AsyncSession):
        """장치 등록."""
        device = await crud.create_device(
            db_session,
            name="거실 조명",
            device_type="light",
            adapter_type="tapo",
            location="거실",
            config={"host": "192.168.0.10"},
        )
        assert device.id is not None
        assert device.name == "거실 조명"
        assert device.config["host"] == "192.168.0.10"
        assert device.is_active is True

    @pytest.mark.asyncio
    async def test_get_device_by_name(self, db_session: AsyncSession):
        """이름으로 장치 조회."""
        await crud.create_device(
            db_session,
            name="침실 조명",
            device_type="light",
            adapter_type="tapo",
            location="침실",
        )
        await db_session.flush()

        found = await crud.get_device_by_name(db_session, name="침실 조명")
        assert found is not None
        assert found.name == "침실 조명"

    @pytest.mark.asyncio
    async def test_get_device_by_name_not_found(self, db_session: AsyncSession):
        """존재하지 않는 장치 조회."""
        found = await crud.get_device_by_name(db_session, name="없는 장치")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_all_devices(self, db_session: AsyncSession):
        """전체 장치 조회."""
        await crud.create_device(
            db_session, name="장치1", device_type="light",
            adapter_type="tapo", location="거실",
        )
        await crud.create_device(
            db_session, name="장치2", device_type="plug",
            adapter_type="tapo", location="침실",
        )
        await db_session.flush()

        devices = await crud.get_all_devices(db_session)
        assert len(devices) == 2


class TestTapoAdapter:
    """Tapo 어댑터 테스트."""

    @pytest.mark.asyncio
    async def test_connect(self):
        """연결 테스트."""
        adapter = TapoAdapter()
        await adapter.connect({"host": "192.168.0.10"})
        assert adapter._host == "192.168.0.10"

    @pytest.mark.asyncio
    async def test_execute_on(self):
        """ON 액션."""
        adapter = TapoAdapter()
        await adapter.connect({"host": "192.168.0.10"})
        result = await adapter.execute("on")
        assert result["status"] == "on"

    @pytest.mark.asyncio
    async def test_execute_off(self):
        """OFF 액션."""
        adapter = TapoAdapter()
        await adapter.connect({"host": "192.168.0.10"})
        result = await adapter.execute("off")
        assert result["status"] == "off"

    @pytest.mark.asyncio
    async def test_execute_unsupported_action(self):
        """지원하지 않는 액션."""
        adapter = TapoAdapter()
        await adapter.connect({"host": "192.168.0.10"})
        with pytest.raises(DeviceError, match="Unsupported action"):
            await adapter.execute("dance")

    @pytest.mark.asyncio
    async def test_turn_on_without_host(self):
        """호스트 없이 켜기 시도."""
        adapter = TapoAdapter()
        with pytest.raises(DeviceOfflineError):
            await adapter.turn_on()


class TestDeviceService:
    """장치 서비스 테스트."""

    @pytest.mark.asyncio
    async def test_register_device(self, db_session: AsyncSession):
        """장치 등록."""
        service = DeviceService(db_session)
        device = await service.register_device(
            name="테스트 조명",
            device_type="light",
            adapter_type="tapo",
            location="거실",
            config={"host": "192.168.0.10"},
        )
        assert device.name == "테스트 조명"

    @pytest.mark.asyncio
    async def test_control_device_not_found(self, db_session: AsyncSession):
        """존재하지 않는 장치 제어."""
        service = DeviceService(db_session)
        with pytest.raises(DeviceError, match="Device not found"):
            await service.control_device(
                device_name="없는 장치", action="on"
            )

    @pytest.mark.asyncio
    async def test_control_device_unsupported_adapter(self, db_session: AsyncSession):
        """지원하지 않는 어댑터."""
        await crud.create_device(
            db_session,
            name="미지원 장치",
            device_type="light",
            adapter_type="zigbee",
            location="거실",
        )
        await db_session.flush()

        service = DeviceService(db_session)
        with pytest.raises(DeviceError, match="Unsupported adapter"):
            await service.control_device(
                device_name="미지원 장치", action="on"
            )

    @pytest.mark.asyncio
    async def test_control_device_success(self, db_session: AsyncSession):
        """장치 제어 성공."""
        await crud.create_device(
            db_session,
            name="거실 조명",
            device_type="light",
            adapter_type="tapo",
            location="거실",
            config={"host": "192.168.0.10"},
        )
        await db_session.flush()

        service = DeviceService(db_session)
        result = await service.control_device(
            device_name="거실 조명", action="on"
        )
        assert result["status"] == "on"
