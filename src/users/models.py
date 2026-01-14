"""User database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class OAuthProvider(str, Enum):
    """OAuth provider types."""

    GOOGLE = "google"
    APPLE = "apple"


class Gender(str, Enum):
    """Gender types."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


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

    # Onboarding fields
    age: int | None = Field(default=None)
    gender: Gender | None = Field(default=None)
    terms_agreed: bool = Field(default=False)
    terms_agreed_at: datetime | None = Field(default=None)
    onboarding_completed: bool = Field(default=False)

    # Refresh token for JWT
    refresh_token: str | None = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default=None)
