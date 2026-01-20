from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from src.auth import constants, schemas, service
from src.common.responses import (
    ERROR_400_BAD_REQUEST,
    ERROR_401_UNAUTHORIZED,
    ERROR_404_NOT_FOUND,
    ERROR_501_NOT_IMPLEMENTED,
)
from src.config import settings
from src.security import create_access_token, create_refresh_token, verify_token
from src.users import service as user_service
from src.users.dependencies import SessionDep

router = APIRouter()


@router.get(
    "/google",
    summary="Google OAuth 로그인",
    description="사용자를 Google OAuth2 인증 페이지로 리디렉션합니다. 성공 시 설정된 콜백 URL로 리디렉션됩니다.",
    responses={
        307: {"description": "Google 인증 페이지로 리디렉션"},
        501: ERROR_501_NOT_IMPLEMENTED,
    },
)
async def google_login():
    """Redirects the user to the Google OAuth login page."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured",
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
    description="Google로부터 리디렉션된 후 인증 코드를 처리합니다. 신규 사용자인 경우 계정을 생성하고, 기존 사용자인 경우 로그인 처리 후 JWT 액세스 토큰과 리프레시 토큰을 발급합니다.",
    responses={400: ERROR_400_BAD_REQUEST, 501: ERROR_501_NOT_IMPLEMENTED},
)
async def google_callback(code: str, session: SessionDep):
    """
    Handles the Google OAuth callback after user authentication.
    It exchanges the code for tokens, gets user info, creates or logs in the user,
    and returns JWT access and refresh tokens.

    - **code**: The authorization code provided by Google.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured",
        )

    try:
        return await service.google_oauth_flow(code=code, session=session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/refresh",
    response_model=schemas.Token,
    summary="액세스 토큰 갱신",
    description="유효한 리프레시 토큰을 사용하여 새로운 액세스 토큰과 리프레시 토큰을 발급받습니다. (Refresh Token Rotation)",
    responses={
        400: ERROR_400_BAD_REQUEST,
        401: ERROR_401_UNAUTHORIZED,
        404: ERROR_404_NOT_FOUND,
    },
)
async def refresh_access_token(request: schemas.RefreshTokenRequest, session: SessionDep):
    """
    Refreshes an access token using a valid refresh token (implements Refresh Token Rotation).

    - **refresh_token**: The user's valid refresh token.
    """
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.refresh_token != request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or already used",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

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
    description="사용자의 리프레시 토큰을 무효화하여 로그아웃 처리합니다.",
    responses={401: ERROR_401_UNAUTHORIZED},
)
async def logout(request: schemas.LogoutRequest, session: SessionDep):
    """
    Logs out the user by invalidating their refresh token.

    - **refresh_token**: The user's refresh token to invalidate.
    """
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if user:
        await user_service.update_refresh_token(session=session, db_user=user, refresh_token="")

    return None