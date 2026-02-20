"""Authentication schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.users.schemas import OAuthProvider


class OAuthUserCreate(BaseModel):
    """Schema for creating a user from OAuth."""

    email: str = Field(..., description="사용자 이메일")
    full_name: str | None = Field(None, description="사용자 이름")
    oauth_provider: OAuthProvider = Field(..., description="OAuth 제공자 (google, apple)")
    oauth_provider_id: str = Field(..., description="OAuth 제공자 ID")
    profile_image_url: str | None = Field(None, description="프로필 이미지 URL")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "full_name": "홍길동",
                "oauth_provider": "google",
                "oauth_provider_id": "1234567890",
                "profile_image_url": "https://example.com/profile.jpg",
            }
        }
    )


class OAuthTokenRequest(BaseModel):
    """임시 인증 코드로 토큰 교환 요청"""

    code: str = Field(..., description="OAuth 콜백에서 받은 임시 인증 코드")
    platform: Literal["web", "mobile"] = Field("web", description="플랫폼 (web: 쿠키, mobile: body)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "a1b2c3d4e5f6...",
                "platform": "web",
            }
        }
    )


class GoogleMobileLoginRequest(BaseModel):
    """모바일 Google 로그인 요청 (네이티브 SDK id_token)"""

    id_token: str = Field(..., description="Google Sign-In SDK에서 받은 ID 토큰")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class AppleMobileLoginRequest(BaseModel):
    """모바일 Apple 로그인 요청 (네이티브 SDK)"""

    id_token: str = Field(..., description="Apple Sign-In SDK에서 받은 ID 토큰")
    full_name: str | None = Field(None, description="사용자 이름 (최초 로그인 시에만)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "full_name": "홍길동",
            }
        }
    )


class MobileTokenResponse(BaseModel):
    """모바일 토큰 응답 (refresh_token body 포함)"""

    is_new_user: bool = Field(..., description="신규 사용자 여부")
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_new_user": True,
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )
