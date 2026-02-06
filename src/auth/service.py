"""Authentication service layer - OAuth and JWT logic."""

from datetime import datetime, timedelta, timezone

import httpx
import json
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import constants
from src.auth.schemas import OAuthCallbackResponse, OAuthUserCreate
from src.config import settings
from src.security import create_access_token, create_refresh_token
from src.users import service as user_service
from src.users.models import OAuthProvider, User


async def google_oauth_flow(code: str, session: AsyncSession) -> OAuthCallbackResponse:
    """
    Complete Google OAuth flow.

    1. Exchange code for access token
    2. Get user info from Google
    3. Check if user exists:
       - Existing user: Return JWT tokens
       - New user: Create active user with auto-accepted terms and return JWT tokens
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
        session=session, provider=OAuthProvider.google, provider_id=google_id
    )

    # Existing user - return JWT tokens
    if existing_user:
        access_token_jwt = create_access_token(subject=str(existing_user.id))
        refresh_token_jwt = create_refresh_token(subject=str(existing_user.id))

        await user_service.update_tokens(
            session=session,
            db_user=existing_user,
            refresh_token=refresh_token_jwt,
        )

        return OAuthCallbackResponse(
            is_new_user=False,
            access_token=access_token_jwt,
            refresh_token=refresh_token_jwt,
        )

    # New user - create active user with auto-accepted terms
    new_user = await create_oauth_user(
        session=session,
        oauth_user=OAuthUserCreate(
            email=email,
            full_name=user_data.get("name"),
            oauth_provider=OAuthProvider.google,
            oauth_provider_id=google_id,
            profile_image_url=user_data.get("picture"),
        ),
    )

    # Generate JWT tokens for new user
    access_token_jwt = create_access_token(subject=str(new_user.id))
    refresh_token_jwt = create_refresh_token(subject=str(new_user.id))

    # Store tokens
    await user_service.update_refresh_token(
        session=session, db_user=new_user, refresh_token=refresh_token_jwt
    )

    return OAuthCallbackResponse(
        is_new_user=True,
        access_token=access_token_jwt,
        refresh_token=refresh_token_jwt,
    )


async def create_oauth_user(
    *, session: AsyncSession, oauth_user: OAuthUserCreate
) -> User:
    """
    Create a new user from OAuth provider.
    User is created as active with terms automatically accepted.
    """
    db_obj = User(
        email=oauth_user.email,
        full_name=oauth_user.full_name,
        oauth_provider=oauth_user.oauth_provider,
        oauth_provider_id=oauth_user.oauth_provider_id,
        profile_image_url=oauth_user.profile_image_url,
        is_active=True,  # Immediately active
        terms_agreed=True,  # Auto-accept terms on signup
        terms_agreed_at=datetime.now(timezone.utc),  # Record terms agreement timestamp
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


def generate_apple_client_secret() -> str:
    """
    Generate Apple Client Secret (JWT).
    Required to exchange authorization code for access token.
    """
    if (
        not settings.APPLE_CLIENT_ID
        or not settings.APPLE_TEAM_ID
        or not settings.APPLE_KEY_ID
        or not settings.APPLE_PRIVATE_KEY
    ):
        raise ValueError("Apple OAuth is not correctly configured locally.")

    now = datetime.now(timezone.utc)
    headers = {"kid": settings.APPLE_KEY_ID}
    payload = {
        "iss": settings.APPLE_TEAM_ID,
        "iat": now,
        "exp": now + timedelta(days=180),  # Max 6 months
        "aud": "https://appleid.apple.com",
        "sub": settings.APPLE_CLIENT_ID,
    }

    # The private key might be stored with literal \n characters in env
    private_key = settings.APPLE_PRIVATE_KEY.replace("\\n", "\n")

    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


async def apple_oauth_flow(
    code: str, user_json: str | None, session: AsyncSession
) -> OAuthCallbackResponse:
    """
    Complete Apple OAuth flow.

    1. Generate client secret (ES256 JWT)
    2. Exchange code for access token & ID token
    3. Decode ID token to get email and sub (Apple ID)
    4. Handle first-time login: extract name from user_json
    5. Find or create user
    """
    client_secret = generate_apple_client_secret()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            constants.APPLE_TOKEN_URL,
            data={
                "client_id": settings.APPLE_CLIENT_ID,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.APPLE_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            error_details = response.text
            raise ValueError(f"Failed to exchange code for token: {error_details}")

        token_data = response.json()
        id_token = token_data.get("id_token")

        if not id_token:
            raise ValueError("No id_token in response from Apple")

        try:
            jwks_client = jwt.PyJWKClient("https://appleid.apple.com/auth/keys")
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)

            decoded = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
                issuer="https://appleid.apple.com",
            )
        except Exception as e:
            raise ValueError(f"Invalid id_token: {str(e)}")

        apple_sub = decoded.get("sub")
        email = decoded.get("email")

        if not apple_sub or not email:
            raise ValueError("id_token missing sub or email")

    full_name = ""
    if user_json:
        try:
            user_data = json.loads(user_json)
            name_obj = user_data.get("name", {})
            
            full_name = name_obj.get("firstName", "")
            full_name += name_obj.get("lastName", "")
                
        except json.JSONDecodeError:
            pass

    # Check existing user
    existing_user = await user_service.get_user_by_oauth(
        session=session, provider=OAuthProvider.apple, provider_id=apple_sub
    )

    if existing_user:
        access_token_jwt = create_access_token(subject=str(existing_user.id))
        refresh_token_jwt = create_refresh_token(subject=str(existing_user.id))

        await user_service.update_tokens(
            session=session, db_user=existing_user, refresh_token=refresh_token_jwt
        )

        return OAuthCallbackResponse(
            is_new_user=False,
            access_token=access_token_jwt,
            refresh_token=refresh_token_jwt,
        )

    # Create new user
    new_user = await create_oauth_user(
        session=session,
        oauth_user=OAuthUserCreate(
            email=email,
            full_name=full_name,  # might be None if not first login or skipped
            oauth_provider=OAuthProvider.apple,
            oauth_provider_id=apple_sub,
            profile_image_url=None,  # Apple doesn't provide avatar
        ),
    )

    access_token_jwt = create_access_token(subject=str(new_user.id))
    refresh_token_jwt = create_refresh_token(subject=str(new_user.id))

    await user_service.update_refresh_token(
        session=session, db_user=new_user, refresh_token=refresh_token_jwt
    )

    return OAuthCallbackResponse(
        is_new_user=True,
        access_token=access_token_jwt,
        refresh_token=refresh_token_jwt,
    )