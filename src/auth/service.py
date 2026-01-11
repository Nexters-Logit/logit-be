"""Authentication service layer - OAuth and JWT logic."""

import httpx
from sqlmodel import Session

from src.auth import constants
from src.auth.schemas import OAuthUserCreate, Token
from src.core import create_access_token, create_refresh_token, settings
from src.users import service as user_service
from src.users.models import OAuthProvider, User


async def google_oauth_flow(code: str, session: Session) -> Token:
    """
    Complete Google OAuth flow.

    1. Exchange code for access token
    2. Get user info from Google
    3. Create or get user from database
    4. Generate JWT tokens
    """
    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_response = await client.post(
            constants.GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

        if token_response.status_code != 200:
            raise ValueError("Failed to get access token from Google")

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        # Get user info from Google
        user_response = await client.get(
            constants.GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_response.status_code != 200:
            raise ValueError("Failed to get user info from Google")

        user_data = user_response.json()

    # Check if user exists
    google_id = user_data.get("id")
    email = user_data.get("email")

    user = user_service.get_user_by_oauth(
        session=session, provider=OAuthProvider.GOOGLE, provider_id=google_id
    )

    # Create new user if doesn't exist
    if not user:
        user = create_oauth_user(
            session=session,
            oauth_user=OAuthUserCreate(
                email=email,
                full_name=user_data.get("name"),
                oauth_provider=OAuthProvider.GOOGLE,
                oauth_provider_id=google_id,
                profile_image_url=user_data.get("picture"),
            ),
        )

    # Generate JWT tokens
    access_token_jwt = create_access_token(subject=str(user.id))
    refresh_token_jwt = create_refresh_token(subject=str(user.id))

    # Store refresh token
    user_service.update_refresh_token(
        session=session, db_user=user, refresh_token=refresh_token_jwt
    )

    return Token(access_token=access_token_jwt, refresh_token=refresh_token_jwt)


def create_oauth_user(*, session: Session, oauth_user: OAuthUserCreate) -> User:
    """Create a new user from OAuth provider."""
    db_obj = User(
        email=oauth_user.email,
        full_name=oauth_user.full_name,
        oauth_provider=oauth_user.oauth_provider,
        oauth_provider_id=oauth_user.oauth_provider_id,
        profile_image_url=oauth_user.profile_image_url,
        is_active=True,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj
