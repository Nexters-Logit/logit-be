"""User schemas."""

from datetime import datetime

from sqlmodel import SQLModel

from src.users.models import OAuthProvider


class UserBase(SQLModel):
    """Base user properties."""

    email: str
    full_name: str | None = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str | None = None
    is_active: bool = True


class UserUpdate(SQLModel):
    """Schema for updating a user."""

    email: str | None = None
    full_name: str | None = None
    password: str | None = None


class UserPublic(UserBase):
    """Schema for user public data."""

    id: int
    oauth_provider: OAuthProvider | None = None
    profile_image_url: str | None = None
    created_at: datetime
    is_active: bool


# Re-export OAuthProvider for convenience
__all__ = ["UserBase", "UserCreate", "UserUpdate", "UserPublic", "OAuthProvider"]
