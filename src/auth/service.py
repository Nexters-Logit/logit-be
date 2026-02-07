"""Authentication service layer - OAuth and JWT logic."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import constants
from src.auth.schemas import OAuthUserCreate
from src.config import settings
from src.security import create_access_token, create_refresh_token
from src.users import service as user_service
from src.users.models import OAuthProvider, User

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


# ─── 공용 헬퍼 ───


async def _find_or_create_user(
    session: AsyncSession,
    provider: OAuthProvider,
    provider_id: str,
    email: str,
    name: str | None,
    picture: str | None,
) -> tuple[User, bool]:
    """
    OAuth 사용자 조회 또는 생성.
    Returns (user, is_new_user)
    """
    existing_user = await user_service.get_user_by_oauth(
        session=session, provider=provider, provider_id=provider_id
    )

    if existing_user:
        return existing_user, False

    new_user = await create_oauth_user(
        session=session,
        oauth_user=OAuthUserCreate(
            email=email,
            full_name=name,
            oauth_provider=provider,
            oauth_provider_id=provider_id,
            profile_image_url=picture,
        ),
    )
    return new_user, True


async def _generate_tokens_for_user(
    session: AsyncSession, user: User, is_new_user: bool
) -> dict:
    """사용자에 대한 JWT 토큰 생성 및 DB 저장."""
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    await user_service.update_refresh_token(
        session=session, db_user=user, refresh_token=refresh_token
    )

    return {
        "is_new_user": is_new_user,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


# ─── Google OAuth ───


async def google_oauth_flow(code: str, session: AsyncSession) -> dict:
    """
    웹용 Google OAuth flow.
    Authorization code → access token → user info → JWT 토큰 발급.
    """
    async with httpx.AsyncClient() as client:
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

        user_response = await client.get(
            constants.GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_response.status_code != 200:
            raise ValueError("Failed to get user info from Google")

        user_data = user_response.json()

    user, is_new_user = await _find_or_create_user(
        session=session,
        provider=OAuthProvider.google,
        provider_id=user_data.get("id"),
        email=user_data.get("email"),
        name=user_data.get("name"),
        picture=user_data.get("picture"),
    )

    return await _generate_tokens_for_user(session, user, is_new_user)


async def google_mobile_auth_flow(id_token: str, session: AsyncSession) -> dict:
    """
    모바일용 Google 로그인.
    네이티브 SDK에서 받은 id_token을 검증하고 JWT 토큰 발급.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_TOKENINFO_URL,
            params={"id_token": id_token},
        )

        if response.status_code != 200:
            raise ValueError("Invalid Google ID token")

        token_info = response.json()

    if token_info.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise ValueError("Invalid token audience")

    user, is_new_user = await _find_or_create_user(
        session=session,
        provider=OAuthProvider.google,
        provider_id=token_info.get("sub"),
        email=token_info.get("email"),
        name=token_info.get("name"),
        picture=token_info.get("picture"),
    )

    return await _generate_tokens_for_user(session, user, is_new_user)


# ─── Apple OAuth ───


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
        "exp": now + timedelta(days=180),
        "aud": "https://appleid.apple.com",
        "sub": settings.APPLE_CLIENT_ID,
    }

    private_key = settings.APPLE_PRIVATE_KEY.replace("\\n", "\n")

    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


async def apple_oauth_flow(
    code: str, user_json: str | None, session: AsyncSession
) -> dict:
    """
    웹용 Apple OAuth flow.
    Authorization code → id_token → 사용자 조회/생성 → JWT 토큰 발급.
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

    user, is_new_user = await _find_or_create_user(
        session=session,
        provider=OAuthProvider.apple,
        provider_id=apple_sub,
        email=email,
        name=full_name or None,
        picture=None,
    )

    return await _generate_tokens_for_user(session, user, is_new_user)


async def apple_mobile_auth_flow(
    id_token: str, full_name: str | None, session: AsyncSession
) -> dict:
    """
    모바일용 Apple 로그인.
    네이티브 SDK에서 받은 id_token을 JWKS로 검증하고 JWT 토큰 발급.
    """
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
        raise ValueError(f"Invalid Apple ID token: {str(e)}")

    apple_sub = decoded.get("sub")
    email = decoded.get("email")

    if not apple_sub or not email:
        raise ValueError("id_token missing sub or email")

    user, is_new_user = await _find_or_create_user(
        session=session,
        provider=OAuthProvider.apple,
        provider_id=apple_sub,
        email=email,
        name=full_name,
        picture=None,
    )

    return await _generate_tokens_for_user(session, user, is_new_user)


# ─── OAuth 사용자 생성 ───


async def create_oauth_user(
    *, session: AsyncSession, oauth_user: OAuthUserCreate
) -> User:
    """OAuth 사용자 생성. 즉시 활성화 + 약관 자동 동의."""
    db_obj = User(
        email=oauth_user.email,
        full_name=oauth_user.full_name,
        oauth_provider=oauth_user.oauth_provider,
        oauth_provider_id=oauth_user.oauth_provider_id,
        profile_image_url=oauth_user.profile_image_url,
        is_active=True,
        terms_agreed=True,
        terms_agreed_at=datetime.now(timezone.utc),
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
