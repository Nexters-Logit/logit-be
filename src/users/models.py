"""User database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class OAuthProvider(str, Enum):
    """OAuth provider types."""

    GOOGLE = "google"
    APPLE = "apple"


class User(SQLModel, table=True):
    """User database model."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    hashed_password: str | None = Field(default=None)  # Nullable for OAuth users

    # OAuth fields
    oauth_provider: OAuthProvider | None = Field(default=None)
    oauth_provider_id: str | None = Field(default=None, index=True)
    profile_image_url: str | None = Field(default=None)

    # Refresh token for JWT
    refresh_token: str | None = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default=None)
