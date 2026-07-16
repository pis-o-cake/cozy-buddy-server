"""디바이스 토큰·JWT 유틸 (설계서 §11).

- 페어링 시 발급하는 device token은 평문을 1회만 반환하고 서버에는 SHA-256 해시만 저장.
- 허브 WS/REST 인증은 device token → 단기 JWT 교환으로 수행.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import get_settings
from app.core.exceptions import UnauthorizedError

_JWT_ALGORITHM = "HS256"


def generate_pairing_code() -> str:
    """6자리 숫자 페어링 코드를 생성한다 (허브 화면 입력용)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_device_token() -> str:
    """256bit 무작위 device token을 생성한다. 평문은 페어링 응답으로 1회만 노출."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """저장용 토큰 해시. 원문 대조는 항상 해시 비교로만 수행한다."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_jwt(hub_id: str) -> str:
    """허브 세션용 단기 JWT를 발급한다.

    Args:
        hub_id: 페어링된 허브 식별자 ("living-01" 형태).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": hub_id,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expires_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    """JWT를 검증하고 페이로드를 반환한다.

    Raises:
        UnauthorizedError: 서명 불일치·만료 등 모든 검증 실패.
    """
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(f"jwt verification failed: {exc}") from exc
