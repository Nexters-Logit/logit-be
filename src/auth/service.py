"""Authentication service layer - OAuth and JWT logic."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import constants
from src.auth.schemas import OAuthCallbackResponse, OAuthUserCreate
from src.config import settings
from src.security import create_access_token, create_onboarding_token, create_refresh_token
from src.users import service as user_service
from src.users.models import OAuthProvider, User


async def google_oauth_flow(code: str, session: AsyncSession) -> OAuthCallbackResponse:
    """
    Complete Google OAuth flow.

    1. Exchange code for access token
    2. Get user info from Google
    3. Check if user exists:
       - Existing user with onboarding complete: Return full JWT tokens
       - Existing user without onboarding: Return onboarding token
       - New user: Create user and return onboarding token
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

    google_id = user_data.get("id")
    email = user_data.get("email")

    # Check if user exists
    existing_user = await user_service.get_user_by_oauth(
        session=session, provider=OAuthProvider.GOOGLE, provider_id=google_id
    )

    # Existing user
    if existing_user:
        # User hasn't completed onboarding yet
        if not existing_user.onboarding_completed:
            return OAuthCallbackResponse(
                is_new_user=False,
                requires_onboarding=True,
                onboarding_token=create_onboarding_token(str(existing_user.id)),
                user_info={
                    "email": existing_user.email,
                    "name": existing_user.full_name,
                    "profile_image": existing_user.profile_image_url,
                },
            )

        # User has completed onboarding - normal login
        access_token_jwt = create_access_token(subject=str(existing_user.id))
        refresh_token_jwt = create_refresh_token(subject=str(existing_user.id))

        await user_service.update_refresh_token(
            session=session, db_user=existing_user, refresh_token=refresh_token_jwt
        )

        return OAuthCallbackResponse(
            is_new_user=False,
            requires_onboarding=False,
            access_token=access_token_jwt,
            refresh_token=refresh_token_jwt,
        )

    # New user - create incomplete user account
    new_user = await create_incomplete_oauth_user(
        session=session,
        oauth_user=OAuthUserCreate(
            email=email,
            full_name=user_data.get("name"),
            oauth_provider=OAuthProvider.GOOGLE,
            oauth_provider_id=google_id,
            profile_image_url=user_data.get("picture"),
        ),
    )

    # Return onboarding token for new user
    onboarding_token = create_onboarding_token(str(new_user.id))

    return OAuthCallbackResponse(
        is_new_user=True,
        requires_onboarding=True,
        onboarding_token=onboarding_token,
        user_info={
            "email": new_user.email,
            "name": new_user.full_name,
            "profile_image": new_user.profile_image_url,
        },
    )


async def create_incomplete_oauth_user(
    *, session: AsyncSession, oauth_user: OAuthUserCreate
) -> User:
    """
    Create a new user from OAuth provider.
    User is created in incomplete state - requires onboarding.
    """
    db_obj = User(
        email=oauth_user.email,
        full_name=oauth_user.full_name,
        oauth_provider=oauth_user.oauth_provider,
        oauth_provider_id=oauth_user.oauth_provider_id,
        profile_image_url=oauth_user.profile_image_url,
        is_active=False,  # Inactive until onboarding is completed
        onboarding_completed=False,
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj