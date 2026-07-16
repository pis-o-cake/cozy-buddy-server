"""auth 도메인 서비스 — 페어링 → device token → JWT (설계서 §11).

페어링 코드는 TTL이 짧은 일회성 값이라 in-memory로 관리한다(단일 프로세스 전제 —
멀티 워커 전환 시 Redis 등으로 교체 지점).
"""

import time
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PairingCodeInvalidError,
    UnauthorizedError,
)
from app.core.security import create_jwt, generate_device_token, generate_pairing_code, hash_token
from app.domain.auth import crud
from app.domain.auth.models import Hub


class PairingCodeStore:
    """발급된 페어링 코드와 만료 시각. asyncio 단일 루프 전제라 잠금 불필요."""

    def __init__(self) -> None:
        self._codes: dict[str, float] = {}

    def issue(self, ttl_seconds: int) -> str:
        self._evict_expired()
        code = generate_pairing_code()
        self._codes[code] = time.monotonic() + ttl_seconds
        return code

    def consume(self, code: str) -> bool:
        """코드를 검증하고 소모한다. 유효하면 True (일회성 — 재사용 불가)."""
        self._evict_expired()
        return self._codes.pop(code, None) is not None

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [c for c, exp in self._codes.items() if exp <= now]
        for code in expired:
            del self._codes[code]


_pairing_codes = PairingCodeStore()


def issue_pairing_code() -> tuple[str, int]:
    """새 페어링 코드를 발급한다. Returns: (코드, TTL초)."""
    ttl = get_settings().pairing_code_ttl_seconds
    code = _pairing_codes.issue(ttl)
    logger.info("pairing code issued (ttl={}s)", ttl)
    return code, ttl


async def pair_hub(session: AsyncSession, *, code: str, hub_id: str, name: str) -> tuple[Hub, str]:
    """페어링 코드를 검증하고 허브를 등록한다.

    Returns:
        (Hub, 평문 device token) — 토큰 평문은 이 반환에서만 존재하고 저장되지 않는다.

    Raises:
        PairingCodeInvalidError: 코드 불일치/만료.
        ConflictError: 이미 등록된 hub_id.
    """
    if not _pairing_codes.consume(code):
        raise PairingCodeInvalidError(f"invalid or expired pairing code for hub '{hub_id}'")
    if await crud.get_hub_by_hub_id(session, hub_id) is not None:
        raise ConflictError(f"hub '{hub_id}' already paired")

    token = generate_device_token()
    hub = await crud.create_hub(session, hub_id=hub_id, name=name, token_hash=hash_token(token))
    logger.info("hub paired: {}", hub_id)
    return hub, token


async def issue_hub_jwt(session: AsyncSession, device_token: str) -> tuple[str, int]:
    """device token을 검증하고 단기 JWT를 발급한다. last_seen_at 갱신 포함.

    Raises:
        UnauthorizedError: 토큰 불일치(폐기 포함).
    """
    hub = await crud.get_hub_by_token_hash(session, hash_token(device_token))
    if hub is None:
        raise UnauthorizedError("unknown device token")

    hub.last_seen_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    expires_in = get_settings().jwt_expires_hours * 3600
    return create_jwt(hub.hub_id), expires_in


async def unpair_hub(session: AsyncSession, hub_id: str) -> None:
    """허브 등록을 해제한다(토큰 즉시 무효화 — 설계서 §11).

    Raises:
        NotFoundError: 등록되지 않은 hub_id.
    """
    hub = await crud.get_hub_by_hub_id(session, hub_id)
    if hub is None:
        raise NotFoundError(f"hub '{hub_id}' not found")
    await crud.delete_hub(session, hub)
    logger.info("hub unpaired: {}", hub_id)
