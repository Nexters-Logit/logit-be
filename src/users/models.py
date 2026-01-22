"""User database models."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class OAuthProvider(str, Enum):
    """OAuth provider types."""

    GOOGLE = "google"
    APPLE = "apple"


class User(SQLModel, table=True):
    """User database model."""

    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    # OAuth fields (OAuth only - no password authentication)
    oauth_provider: OAuthProvider | None = Field(default=None, index=True)
    oauth_provider_id: str | None = Field(default=None, index=True)
    profile_image_url: str | None = Field(default=None)

    # Terms agreement (required for legal compliance)
    terms_agreed: bool = Field(default=False)
    terms_agreed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # JWT tokens
    access_token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)

    # Timestamps
    # All datetimes are stored in UTC and include timezone info
    # PostgreSQL TIMESTAMP WITH TIME ZONE stores internally as UTC
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )
