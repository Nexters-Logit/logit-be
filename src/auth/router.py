"""인증 API 엔드포인트"""

import json
import secrets
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, Header, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.auth import constants, schemas, service
from src.auth.exceptions import OAuthError, OAuthProviderNotConfiguredError
from src.auth.utils import get_frontend_callback_url, get_oauth_redirect_uri
from src.common.responses import (
    ERROR_400_BAD_REQUEST,
    ERROR_401_UNAUTHORIZED,
    ERROR_404_NOT_FOUND,
    ERROR_501_NOT_IMPLEMENTED,
    create_responses,
)
from src.config import settings
from src.database import get_redis
from src.exceptions import AuthenticationError, InactiveUserError, UserNotFoundError
from src.security import create_access_token, create_refresh_token, verify_token
from src.users import service as user_service
from src.users.dependencies import SessionDep

router = APIRouter()


# ─── 내부 헬퍼 ───


def _extract_bearer_token(authorization: str | None) -> str | None:
    """Authorization 헤더에서 Bearer 토큰 추출."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


def _cookie_kwargs() -> dict:
    """환경별 쿠키 보안 설정을 반환한다."""
    is_prod = settings.ENVIRONMENT == "production"
    return {
        "httponly": True,
        "secure": is_prod,
        "samesite": "lax",
        "domain": ".logit.ai.kr" if is_prod else None,
        "path": "/",
    }


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """HttpOnly refresh token 쿠키 설정 (웹 전용)."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **_cookie_kwargs(),
    )


def _delete_refresh_cookie(response: Response) -> None:
    """refresh token 쿠키 삭제."""
    response.delete_cookie(
        key="refresh_token",
        **_cookie_kwargs(),
    )


async def _create_oauth_state(nonce: str | None = None) -> str:
    """OAuth state를 생성하고 Redis에 저장합니다. nonce가 있으면 함께 저장."""
    state = secrets.token_urlsafe(32)
    redis = await get_redis()
    value = nonce or "1"
    await redis.set(f"oauth:state:{state}", value, ex=300)
    return state


async def _verify_oauth_state(state: str) -> str | None:
    """OAuth state를 검증하고 Redis에서 원자적으로 삭제합니다. nonce가 있으면 반환."""
    redis = await get_redis()
    data = await redis.getdel(f"oauth:state:{state}")
    if not data:
        raise OAuthError("Invalid or expired OAuth state.")
    value = data if isinstance(data, str) else data.decode()
    return value if value != "1" else None


async def _store_temp_code_and_redirect(result: dict) -> RedirectResponse:
    """OAuth 결과를 Redis 임시 코드로 저장하고 프론트엔드로 리디렉션."""
    temp_code = secrets.token_urlsafe(32)
    redis = await get_redis()
    await redis.set(
        f"oauth:temp:{temp_code}",
        json.dumps(result),
        ex=60,
    )

    params = urlencode({"code": temp_code})
    return RedirectResponse(
        url=f"{get_frontend_callback_url()}?{params}"
    )


def _error_redirect(detail: str) -> RedirectResponse:
    """에러 메시지와 함께 프론트엔드로 리디렉션."""
    error_params = urlencode({"error": detail})
    return RedirectResponse(
        url=f"{get_frontend_callback_url()}?{error_params}"
    )


# ─── Google OAuth (웹 - 리디렉션 방식) ───


@router.get(
    "/google",
    summary="Google OAuth 로그인 (웹)",
    responses={
        307: {"description": "Google 인증 페이지로 리디렉션"},
        501: ERROR_501_NOT_IMPLEMENTED,
    },
)
async def google_login():
    """
    Google OAuth 로그인 페이지로 리디렉션합니다.
    웹 클라이언트 전용입니다. 모바일은 POST /auth/google/mobile을 사용하세요.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise OAuthProviderNotConfiguredError("Google")

    state = await _create_oauth_state()

    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": get_oauth_redirect_uri("google"),
        "response_type": "code",
        "scope": constants.GOOGLE_SCOPES,
        "state": state,
    })
    google_auth_url = f"{constants.GOOGLE_AUTH_URL}?{params}"

    return RedirectResponse(url=google_auth_url)


@router.get(
    "/google/callback",
    summary="Google OAuth 콜백 처리 (웹)",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {501: ERROR_501_NOT_IMPLEMENTED},
    ),
)
async def google_callback(code: str, state: str, session: SessionDep):
    """
    Google OAuth 콜백을 처리합니다.
    임시 인증 코드를 발급하여 프론트엔드로 리디렉션합니다.
    프론트에서 POST /auth/token으로 토큰을 교환합니다.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise OAuthProviderNotConfiguredError("Google")

    try:
        await _verify_oauth_state(state)
        result = await service.google_oauth_flow(code=code, session=session)
    except Exception:
        return _error_redirect("oauth_failed")

    return await _store_temp_code_and_redirect(result)


# ─── Google OAuth (모바일 - SDK 토큰 방식) ───


@router.post(
    "/google/mobile",
    response_model=schemas.MobileTokenResponse,
    summary="Google 로그인 (모바일)",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {501: ERROR_501_NOT_IMPLEMENTED},
    ),
)
async def google_mobile_login(
    request: schemas.GoogleMobileLoginRequest,
    session: SessionDep,
):
    """
    모바일 네이티브 SDK에서 받은 Google ID 토큰으로 로그인합니다.

    - **id_token**: Google Sign-In SDK에서 받은 ID 토큰
    - 토큰 검증 후 JWT access_token + refresh_token을 body로 반환합니다.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise OAuthProviderNotConfiguredError("Google")

    result = await service.google_mobile_auth_flow(
        id_token=request.id_token, session=session
    )

    return schemas.MobileTokenResponse(**result)


# ─── Apple OAuth (웹 - 리디렉션 방식) ───


@router.get(
    "/apple",
    summary="Apple OAuth 로그인 (웹)",
    responses={
        307: {"description": "Apple 인증 페이지로 리디렉션"},
        501: ERROR_501_NOT_IMPLEMENTED,
    },
)
async def apple_login():
    """
    Apple OAuth 로그인 페이지로 리디렉션합니다.
    웹 클라이언트 전용입니다. 모바일은 POST /auth/apple/mobile을 사용하세요.
    """
    if not settings.APPLE_CLIENT_ID:
        raise OAuthProviderNotConfiguredError("Apple")

    nonce = secrets.token_urlsafe(32)
    state = await _create_oauth_state(nonce=nonce)

    params = urlencode({
        "client_id": settings.APPLE_CLIENT_ID,
        "redirect_uri": get_oauth_redirect_uri("apple"),
        "response_type": "code",
        "response_mode": "form_post",
        "scope": constants.APPLE_SCOPES,
        "state": state,
        "nonce": nonce,
    })
    apple_auth_url = f"{constants.APPLE_AUTH_URL}?{params}"

    return RedirectResponse(url=apple_auth_url)


@router.post(
    "/apple/callback",
    summary="Apple OAuth 콜백 처리 (웹)",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {501: ERROR_501_NOT_IMPLEMENTED},
    ),
)
async def apple_callback(
    session: SessionDep,
    code: str = Form(...),
    state: str = Form(...),
    user: str | None = Form(None),
):
    """
    Apple OAuth 콜백을 처리합니다.
    Apple은 POST 방식으로 콜백을 보냅니다 (form_post).
    임시 인증 코드를 발급하여 프론트엔드로 리디렉션합니다.
    """
    if not settings.APPLE_CLIENT_ID:
        raise OAuthProviderNotConfiguredError("Apple")

    try:
        nonce = await _verify_oauth_state(state)
        result = await service.apple_oauth_flow(
            code=code, user_json=user, session=session, nonce=nonce
        )
    except Exception:
        return _error_redirect("oauth_failed")

    return await _store_temp_code_and_redirect(result)


# ─── Apple OAuth (모바일 - SDK 토큰 방식) ───


@router.post(
    "/apple/mobile",
    response_model=schemas.MobileTokenResponse,
    summary="Apple 로그인 (모바일)",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {501: ERROR_501_NOT_IMPLEMENTED},
    ),
)
async def apple_mobile_login(
    request: schemas.AppleMobileLoginRequest,
    session: SessionDep,
):
    """
    모바일 네이티브 SDK에서 받은 Apple ID 토큰으로 로그인합니다.

    - **id_token**: Apple Sign-In SDK에서 받은 ID 토큰
    - **full_name**: 사용자 이름 (최초 로그인 시에만 Apple이 제공)
    - 토큰 검증 후 JWT access_token + refresh_token을 body로 반환합니다.
    """
    if not settings.APPLE_CLIENT_ID:
        raise OAuthProviderNotConfiguredError("Apple")

    result = await service.apple_mobile_auth_flow(
        id_token=request.id_token,
        full_name=request.full_name,
        session=session,
    )

    return schemas.MobileTokenResponse(**result)


# ─── 임시 코드 → 토큰 교환 (웹/모바일 공용) ───


@router.post(
    "/token",
    summary="임시 코드로 토큰 교환",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
    ),
)
async def exchange_token(request: schemas.OAuthTokenRequest):
    """
    OAuth 콜백에서 받은 임시 인증 코드를 JWT 토큰으로 교환합니다.

    - **code**: 임시 인증 코드 (60초 내 일회용)
    - **platform**: "web"이면 refresh_token은 HttpOnly 쿠키, "mobile"이면 body로 반환
    """
    redis = await get_redis()
    key = f"oauth:temp:{request.code}"
    data = await redis.getdel(key)

    if not data:
        raise OAuthError("Invalid or expired code.")

    token_data = json.loads(data)

    if request.platform == "mobile":
        return JSONResponse(content={
            "is_new_user": token_data["is_new_user"],
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
        })

    # web: refresh_token은 쿠키로
    response = JSONResponse(content={
        "is_new_user": token_data["is_new_user"],
        "access_token": token_data["access_token"],
    })
    _set_refresh_cookie(response, token_data["refresh_token"])
    return response


# ─── 토큰 갱신 ───


@router.post(
    "/refresh",
    summary="액세스 토큰 갱신",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {401: ERROR_401_UNAUTHORIZED},
        {404: ERROR_404_NOT_FOUND},
    ),
)
async def refresh_access_token(
    session: SessionDep,
    authorization: str | None = Header(None),
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
):
    """
    리프레시 토큰으로 새 액세스 토큰을 발급합니다.

    - **모바일**: Authorization: Bearer {refresh_token} 헤더로 요청 → 새 토큰 모두 body로 반환
    - **웹**: 쿠키에서 refresh_token 읽음 → 새 쿠키 설정
    - Refresh Token Rotation 적용 (기존 토큰 무효화)
    """
    # 모바일: Authorization 헤더에서, 웹: 쿠키에서
    bearer_token = _extract_bearer_token(authorization)
    actual_token = bearer_token or refresh_token_cookie
    is_mobile = bearer_token is not None

    if not actual_token:
        raise AuthenticationError("Refresh token not found.")

    user_id = verify_token(actual_token, token_type="refresh")

    if user_id is None:
        raise AuthenticationError("Invalid or expired refresh token.")

    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if not user:
        raise UserNotFoundError()

    if user.refresh_token != actual_token:
        raise AuthenticationError("Refresh token has been revoked or already used.")

    if not user.is_active:
        raise InactiveUserError()

    new_access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))

    await user_service.update_refresh_token(
        session=session, db_user=user, refresh_token=new_refresh_token
    )

    if is_mobile:
        return JSONResponse(content={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
        })

    # web
    response = JSONResponse(content={
        "access_token": new_access_token,
    })
    _set_refresh_cookie(response, new_refresh_token)
    return response


# ─── 로그아웃 ───


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    responses={401: ERROR_401_UNAUTHORIZED},
)
async def logout(
    session: SessionDep,
    authorization: str | None = Header(None),
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
):
    """
    로그아웃을 처리합니다.

    - **모바일**: Authorization: Bearer {refresh_token} 헤더로 요청
    - **웹**: 쿠키에서 refresh_token 읽음
    - DB에서 리프레시 토큰을 삭제하고 쿠키를 제거합니다.
    """
    actual_token = _extract_bearer_token(authorization) or refresh_token_cookie

    if actual_token:
        user_id = verify_token(actual_token, token_type="refresh")
        if user_id:
            user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))
            if user:
                await user_service.update_refresh_token(
                    session=session, db_user=user, refresh_token=""
                )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_refresh_cookie(response)
    return response
