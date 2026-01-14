"""Authentication schemas."""

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
    """OAuth callback response - distinguishes new vs existing users."""

    is_new_user: bool
    requires_onboarding: bool  # Whether additional info is needed

    # For new users: temporary onboarding token
    onboarding_token: str | None = None

    # For existing users: full JWT tokens
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"

    # Basic user info (for onboarding screen)
    user_info: dict | None = None  # {email, name, profile_image}


class CompleteSignupRequest(SQLModel):
    """Complete signup request with additional user info."""

    onboarding_token: str  # Temporary token from OAuth callback
    age: int
    gender: str  # "male", "female", "other", "prefer_not_to_say"
    terms_agreed: bool


class CompleteSignupResponse(SQLModel):
    """Complete signup response with full JWT tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict  # Complete user information
