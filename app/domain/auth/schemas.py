"""auth 도메인 요청/응답 스키마 (설계서 §5-2 auth 엔드포인트)."""

from pydantic import BaseModel, Field


class PairingCodeResponse(BaseModel):
    code: str
    expires_in: int  # 초


class PairRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    hub_id: str = Field(min_length=1, max_length=64)  # 예: "living-01"
    name: str = Field(min_length=1, max_length=100)


class PairResponse(BaseModel):
    hub_id: str
    device_token: str  # 평문은 이 응답에서 1회만 노출 (설계서 §11)


class TokenRequest(BaseModel):
    device_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 초
