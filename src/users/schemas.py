"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.users.models import OAuthProvider


class UserBase(BaseModel):
    """Base user properties."""

    email: str = Field(..., description="사용자 이메일")
    full_name: str | None = Field(None, description="사용자 이름")


class UserCreate(UserBase):
    """Schema for creating a user (OAuth only)."""

    is_active: bool = Field(default=True, description="활성 상태")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "full_name": "홍길동",
                "is_active": True,
            }
        }
    )


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: str | None = Field(None, description="사용자 이메일")
    full_name: str | None = Field(None, description="사용자 이름")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newemail@example.com",
                "full_name": "김철수",
            }
        }
    )


class UserPublic(UserBase):
    """Schema for user public data."""

    id: UUID = Field(..., description="사용자 ID")
    oauth_provider: OAuthProvider | None = Field(None, description="OAuth 제공자 (KAKAO, GOOGLE, APPLE)")
    profile_image_url: str | None = Field(None, description="프로필 이미지 URL")
    created_at: datetime = Field(..., description="가입 시간")
    is_active: bool = Field(..., description="활성 상태")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "full_name": "홍길동",
                "oauth_provider": "KAKAO",
                "profile_image_url": "https://example.com/profile.jpg",
                "created_at": "2024-06-15T10:00:00Z",
                "is_active": True,
            }
        },
    )


# Re-export OAuthProvider for convenience
__all__ = ["UserBase", "UserCreate", "UserUpdate", "UserPublic", "OAuthProvider"]
