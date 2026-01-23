"""Authentication schemas."""

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


class Token(BaseModel):
    """Token response schema."""

    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class TokenPayload(BaseModel):
    """Token payload schema."""

    sub: str | None = Field(None, description="토큰 주체 (사용자 ID)")
    type: str | None = Field(None, description="토큰 타입 (access/refresh)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sub": "123e4567-e89b-12d3-a456-426614174000",
                "type": "access",
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str = Field(..., description="리프레시 토큰")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str = Field(..., description="리프레시 토큰")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class OAuthCallbackResponse(BaseModel):
    """OAuth callback response - returns JWT tokens directly."""

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
