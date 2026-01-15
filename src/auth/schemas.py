"""Authentication schemas."""

from datetime import date

from sqlmodel import SQLModel

from src.users.schemas import OAuthProvider


class OAuthUserCreate(SQLModel):
    """Schema for creating a user from OAuth."""

    email: str
    full_name: str | None = None
    oauth_provider: OAuthProvider
    oauth_provider_id: str
    profile_image_url: str | None = None


class Token(SQLModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    """Token payload schema."""

    sub: str | None = None
    type: str | None = None


class RefreshTokenRequest(SQLModel):
    """Refresh token request."""

    refresh_token: str


class LogoutRequest(SQLModel):
    """Logout request."""

    refresh_token: str


class OAuthCallbackResponse(SQLModel):
    """OAuth callback response - returns JWT tokens directly."""

    is_new_user: bool  # Whether this is a new user signup
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
