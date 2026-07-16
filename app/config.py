"""앱 전역 설정 (설계서 §3-3 교체 매트릭스의 단일 출처).

모든 provider 선택·자격증명은 `.env`로만 주입한다 — 하드코딩 금지 (설계서 §11).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──
    app_name: str = "cozy-buddy-server"
    debug: bool = False
    log_level: str = "INFO"
    default_locale: str = "ko"

    # ── Database ──
    database_url: str = "postgresql+asyncpg://cozy:cozy@localhost:5432/cozy"

    # ── Auth (§11) ──
    jwt_secret: str = "change-me"
    jwt_expires_hours: int = 24
    pairing_code_ttl_seconds: int = 300

    # ── LLM (§3-3 · §7-5) ──
    llm_provider: str = ""  # 비우면 키 구성된 provider 자동 선택
    llm_model: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llamacpp_base_url: str = "http://127.0.0.1:8080/v1"  # Phase 4+ 로컬 슬롯

    # ── Voice (§3-3) ──
    stt_provider: str = "faster-whisper"
    stt_model: str = "large-v3-turbo"
    stt_compute_type: str = "float16"
    stt_confidence_threshold: float = 0.35  # 미달 시 되묻기 (§12-1)
    tts_provider: str = "supertonic"
    tts_voice: str = "M1"
    llm_first_token_timeout_seconds: float = 10.0  # LLM 타임아웃 → 폴백 응답 (§12-1)

    # ── IoT (§8-1) ──
    iot_adapters: str = "kasa,matter"
    kasa_username: str = ""  # Tapo 기기 로컬 핸드셰이크용 계정 (Kasa 구형은 불필요)
    kasa_password: str = ""


@lru_cache
def get_settings() -> Settings:
    """캐시된 설정 인스턴스를 반환한다 (요청마다 재파싱 방지)."""
    return Settings()
