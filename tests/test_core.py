"""core 모듈 테스트."""

import pytest

from app.config import Settings
from app.core.constants import (
    ADAPTER_TAPO,
    DEVICE_TYPE_LIGHT,
    ROLE_ASSISTANT,
    ROLE_USER,
    WS_TYPE_TEXT,
)
from app.core.exceptions import (
    CozyBuddyError,
    DeviceError,
    DeviceOfflineError,
    LLMError,
    ScenarioError,
    VoiceError,
)


class TestExceptions:
    """커스텀 예외 테스트."""

    def test_base_error(self):
        """기본 예외 생성."""
        err = CozyBuddyError(message="테스트 에러", code="TEST")
        assert err.message == "테스트 에러"
        assert err.code == "TEST"
        assert str(err) == "테스트 에러"

    def test_device_error(self):
        """장치 에러."""
        err = DeviceError(message="연결 실패", device_name="거실 조명")
        assert err.device_name == "거실 조명"
        assert err.code == "DEVICE_ERROR"

    def test_device_offline_error(self):
        """장치 오프라인 에러."""
        err = DeviceOfflineError(device_name="침실 조명")
        assert "침실 조명" in err.message
        assert err.device_name == "침실 조명"

    def test_llm_error(self):
        """LLM 에러."""
        err = LLMError(message="모델 로드 실패")
        assert err.code == "LLM_ERROR"

    def test_voice_error(self):
        """음성 에러."""
        err = VoiceError(message="STT 실패")
        assert err.code == "VOICE_ERROR"

    def test_scenario_error(self):
        """시나리오 에러."""
        err = ScenarioError(message="시나리오 없음")
        assert err.code == "SCENARIO_ERROR"


class TestConfig:
    """설정 테스트."""

    def test_default_settings(self):
        """기본 설정값 확인."""
        s = Settings(
            _env_file=None,
            llm_default_provider="vllm",
            vllm_base_url="http://localhost:8080/v1",
        )
        assert s.app_name == "CozyBuddy"
        assert s.app_version == "0.1.0"
        assert s.port == 8000

    def test_rag_defaults(self):
        """RAG 기본 설정."""
        s = Settings(_env_file=None)
        assert s.rag_chunk_size == 500
        assert s.rag_chunk_overlap == 50


class TestConstants:
    """상수 테스트."""

    def test_ws_types(self):
        assert WS_TYPE_TEXT == "text"

    def test_roles(self):
        assert ROLE_USER == "user"
        assert ROLE_ASSISTANT == "assistant"

    def test_device_types(self):
        assert DEVICE_TYPE_LIGHT == "light"
        assert ADAPTER_TAPO == "tapo"
