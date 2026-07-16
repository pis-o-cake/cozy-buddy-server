"""도메인 공통 예외.

내부 예외 메시지는 영어 하드코딩(설계서 §7 로컬라이제이션 규칙).
사용자 응답 문구는 `message_key`로 i18n 레이어(locales/*.json)에서 해석한다.
"""

from typing import Any


class AppError(Exception):
    """HTTP 응답으로 변환되는 도메인 오류의 베이스.

    Attributes:
        status_code: HTTP 상태 코드.
        code: 기계 판독용 오류 코드 (WS/REST 공용 — 설계서 §5-1 error.code).
        message_key: locales/*.json의 사용자 문구 키.
        params: 문구 포맷 파라미터.
    """

    status_code: int = 500
    code: str = "internal_error"
    message_key: str = "errors.internal"

    def __init__(self, detail: str = "", **params: Any) -> None:
        super().__init__(detail or self.code)
        self.params = params


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message_key = "errors.unauthorized"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message_key = "errors.not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message_key = "errors.conflict"


class PairingCodeInvalidError(AppError):
    status_code = 400
    code = "pairing_code_invalid"
    message_key = "errors.pairing_code_invalid"


class ProviderNotConfiguredError(AppError):
    """선택된 provider의 자격증명/설정이 없을 때 (설계서 §7-5)."""

    status_code = 503
    code = "provider_not_configured"
    message_key = "errors.provider_not_configured"


class ProviderNotFoundError(LookupError):
    """레지스트리에 등록되지 않은 provider 이름 (설계서 §3-2 — 영어 하드코딩 예외)."""

    def __init__(self, kind: str, name: str, available: list[str]) -> None:
        listed = ", ".join(available) or "none"
        super().__init__(f"unknown {kind} provider '{name}' (available: {listed})")
