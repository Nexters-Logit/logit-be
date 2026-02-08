"""Authentication service layer - OAuth and JWT logic."""

import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from jwt import PyJWK
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import constants
from src.auth.exceptions import (
    InvalidTokenError,
    OAuthError,
    OAuthProviderNotConfiguredError,
)
from src.auth.schemas import OAuthUserCreate
from src.config import settings
from src.security import create_access_token, create_refresh_token
from src.users import service as user_service
from src.users.models import OAuthProvider, User

# Apple JWKS 비동기 캐시
_apple_jwks_cache: dict | None = None
_apple_jwks_fetched_at: float = 0
_JWKS_CACHE_TTL = 3600  # 1시간


async def _get_apple_jwks() -> dict:
    """Apple JWKS를 비동기로 가져오고 캐싱합니다."""
    global _apple_jwks_cache, _apple_jwks_fetched_at
    now = time.monotonic()
    if _apple_jwks_cache and (now - _apple_jwks_fetched_at) < _JWKS_CACHE_TTL:
        return _apple_jwks_cache

    async with httpx.AsyncClient() as client:
        response = await client.get(constants.APPLE_JWKS_URL)
        if response.status_code != 200:
            if _apple_jwks_cache:
                return _apple_jwks_cache
            raise OAuthError("Failed to fetch Apple JWKS")
        _apple_jwks_cache = response.json()
        _apple_jwks_fetched_at = now
        return _apple_jwks_cache


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
    # 1) 동일 provider + provider_id로 기존 사용자 조회
    existing_user = await user_service.get_user_by_oauth(
        session=session, provider=provider, provider_id=provider_id
    )

    if existing_user:
        return existing_user, False

    # 2) 동일 email이 다른 provider로 이미 가입되어 있는지 확인
    email_user = await user_service.get_user_by_email(
        session=session, email=email
    )

    if email_user:
        raise OAuthError(
            f"이미 {email_user.oauth_provider.value}(으)로 가입된 이메일입니다. "
            f"{email_user.oauth_provider.value} 로그인을 이용해 주세요."
        )

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
            raise OAuthError("Failed to get access token from Google")

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        user_response = await client.get(
            constants.GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_response.status_code != 200:
            raise OAuthError("Failed to get user info from Google")

        user_data = user_response.json()

    provider_id = user_data.get("id")
    email = user_data.get("email")

    if not provider_id or not email:
        raise OAuthError("Google response missing required user fields")

    user, is_new_user = await _find_or_create_user(
        session=session,
        provider=OAuthProvider.google,
        provider_id=provider_id,
        email=email,
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
            constants.GOOGLE_TOKENINFO_URL,
            params={"id_token": id_token},
        )

        if response.status_code != 200:
            raise InvalidTokenError("Invalid Google ID token")

        token_info = response.json()

    if token_info.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise InvalidTokenError("Invalid token audience")

    provider_id = token_info.get("sub")
    email = token_info.get("email")

    if not provider_id or not email:
        raise InvalidTokenError("Google token missing required fields")

    user, is_new_user = await _find_or_create_user(
        session=session,
        provider=OAuthProvider.google,
        provider_id=provider_id,
        email=email,
        name=token_info.get("name"),
        picture=token_info.get("picture"),
    )

    return await _generate_tokens_for_user(session, user, is_new_user)


# ─── Apple OAuth ───


async def _verify_apple_id_token(
    id_token: str, nonce: str | None = None
) -> dict:
    """
    Apple id_token을 비동기 JWKS로 검증하고 디코딩된 페이로드를 반환합니다.
    """
    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"Invalid Apple ID token: {e}") from e

    kid = unverified_header.get("kid")
    jwks_data = await _get_apple_jwks()

    signing_key = None
    for key_data in jwks_data.get("keys", []):
        if key_data.get("kid") == kid:
            signing_key = PyJWK(key_data)
            break

    if not signing_key:
        raise InvalidTokenError("No matching key found in Apple JWKS")

    try:
        decoded = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
        )
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"Invalid Apple ID token: {e}") from e

    if nonce and decoded.get("nonce") != nonce:
        raise InvalidTokenError("Invalid nonce in Apple ID token")

    if not decoded.get("sub") or not decoded.get("email"):
        raise InvalidTokenError("id_token missing sub or email")

    return decoded


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
        raise OAuthProviderNotConfiguredError("Apple")

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
    code: str,
    user_json: str | None,
    session: AsyncSession,
    nonce: str | None = None,
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
            raise OAuthError(f"Failed to exchange code for token: {response.text}")

        token_data = response.json()
        id_token = token_data.get("id_token")

        if not id_token:
            raise OAuthError("No id_token in response from Apple")

        decoded = await _verify_apple_id_token(id_token, nonce=nonce)
        apple_sub = decoded["sub"]
        email = decoded["email"]

    full_name = ""
    if user_json:
        try:
            user_data = json.loads(user_json)
            name_obj = user_data.get("name", {})
            full_name = " ".join(
                filter(None, [name_obj.get("firstName"), name_obj.get("lastName")])
            )
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
    decoded = await _verify_apple_id_token(id_token)
    apple_sub = decoded["sub"]
    email = decoded["email"]

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
