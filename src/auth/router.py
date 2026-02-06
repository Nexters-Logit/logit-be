"""인증 API 엔드포인트"""

from uuid import UUID

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from src.auth import constants, schemas, service
from src.common.responses import (
    RESPONSES_CRUD_WITH_AUTH,
    ERROR_400_BAD_REQUEST,
    ERROR_401_UNAUTHORIZED,
    ERROR_404_NOT_FOUND,
    ERROR_501_NOT_IMPLEMENTED,
    create_responses,
)
from src.config import settings
from src.security import create_access_token, create_refresh_token, verify_token
from src.users import service as user_service
from src.users.dependencies import SessionDep

router = APIRouter()


@router.get(
    "/google",
    summary="Google OAuth 로그인",
    responses={
        307: {"description": "Google 인증 페이지로 리디렉션"},
        501: ERROR_501_NOT_IMPLEMENTED,
    },
)
async def google_login():
    """
    Google OAuth 로그인 페이지로 리디렉션합니다.

    - Google 클라이언트 ID가 설정되지 않은 경우 501 에러를 반환합니다.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured.",
        )

    google_auth_url = (
        f"{constants.GOOGLE_AUTH_URL}?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={constants.GOOGLE_SCOPES}"
    )

    return RedirectResponse(url=google_auth_url)


@router.get(
    "/google/callback",
    response_model=schemas.OAuthCallbackResponse,
    summary="Google OAuth 콜백 처리",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {501: ERROR_501_NOT_IMPLEMENTED},
    ),
)
async def google_callback(code: str, session: SessionDep):
    """
    Google OAuth 콜백을 처리합니다.

    - **code**: Google로부터 받은 인증 코드
    - 인증 코드를 토큰으로 교환하고, 사용자 정보를 조회합니다.
    - 신규 사용자인 경우 계정을 자동 생성합니다.
    - JWT 액세스 토큰과 리프레시 토큰을 발급하여 반환합니다.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured.",
        )

    try:
        result = await service.google_oauth_flow(code=code, session=session)
    except ValueError as e:
        error_params = urlencode({"error": str(e)})
        return RedirectResponse(
            url=f"{settings.FRONTEND_HOST}/auth/callback?{error_params}"
        )

    params = urlencode({
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "is_new_user": str(result.is_new_user).lower(),
    })
    return RedirectResponse(
        url=f"{settings.FRONTEND_HOST}/auth/callback?{params}"
    )


@router.post(
    "/refresh",
    response_model=schemas.Token,
    summary="액세스 토큰 갱신",
    responses=create_responses(
        {400: ERROR_400_BAD_REQUEST},
        {401: ERROR_401_UNAUTHORIZED},
        {404: ERROR_404_NOT_FOUND},
    ),
)
async def refresh_access_token(request: schemas.RefreshTokenRequest, session: SessionDep):
    """
    리프레시 토큰을 사용하여 새로운 토큰을 발급합니다.

    - **refresh_token**: 유효한 리프레시 토큰
    - Refresh Token Rotation 방식을 사용하여 보안을 강화합니다.
    - 이전 리프레시 토큰은 무효화됩니다.
    """
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user.refresh_token != request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or already used.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user.",
        )

    new_access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))

    await user_service.update_refresh_token(
        session=session, db_user=user, refresh_token=new_refresh_token
    )

    return schemas.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    responses={401: ERROR_401_UNAUTHORIZED},
)
async def logout(request: schemas.LogoutRequest, session: SessionDep):
    """
    로그아웃을 처리합니다.

    - **refresh_token**: 무효화할 리프레시 토큰
    - 액세스 토큰과 리프레시 토큰을 모두 무효화하여 즉시 로그아웃 처리합니다.
    """
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if user:
        user_service.update_refresh_token(session=session, db_user=user, refresh_token="")

    return None
