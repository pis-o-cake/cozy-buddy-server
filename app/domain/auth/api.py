"""auth 도메인 API (설계서 §5-2).

라우터 자동등록에 의해 `/api/auth` 프리픽스로 마운트된다.
페어링 코드 발급은 v1 LAN 신뢰 모델에서 무인증 — 외부 노출 시 관리자 인증 추가 지점.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domain.auth import service
from app.domain.auth.schemas import (
    PairingCodeResponse,
    PairRequest,
    PairResponse,
    TokenRequest,
    TokenResponse,
)

router = APIRouter(tags=["auth"])


@router.post("/pairing", response_model=PairingCodeResponse)
async def create_pairing_code() -> PairingCodeResponse:
    """허브 등록용 일회성 페어링 코드를 발급한다 (TTL 설정값, 기본 5분)."""
    code, ttl = service.issue_pairing_code()
    return PairingCodeResponse(code=code, expires_in=ttl)


@router.post("/pair", response_model=PairResponse)
async def pair(body: PairRequest, session: AsyncSession = Depends(get_session)) -> PairResponse:
    """페어링 코드를 제출하고 device token을 발급받는다. 토큰은 이 응답에서 1회만 노출."""
    hub, token = await service.pair_hub(session, code=body.code, hub_id=body.hub_id, name=body.name)
    return PairResponse(hub_id=hub.hub_id, device_token=token)


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    body: TokenRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    """device token → 단기 JWT 교환. WS 연결(설계서 §5-1 auth) 전에 호출한다."""
    jwt_token, expires_in = await service.issue_hub_jwt(session, body.device_token)
    return TokenResponse(access_token=jwt_token, expires_in=expires_in)


@router.delete("/hubs/{hub_id}", status_code=204)
async def unpair(hub_id: str, session: AsyncSession = Depends(get_session)) -> None:
    """허브 등록 해제 — device token 즉시 폐기."""
    await service.unpair_hub(session, hub_id)
