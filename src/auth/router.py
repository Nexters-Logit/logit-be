from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from src.auth import constants, schemas, service
from src.config import settings
from src.security import create_access_token, create_refresh_token, verify_token
from src.users import service as user_service
from src.users.dependencies import SessionDep

router = APIRouter()


@router.get("/google")
async def google_login():
    """
    Redirect to Google OAuth login page.
    Initiates the OAuth flow with Google.
    """
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


@router.get("/google/callback", response_model=schemas.OAuthCallbackResponse)
async def google_callback(code: str, session: SessionDep):
    """
    Handle Google OAuth callback.

    Returns JWT tokens (access_token + refresh_token) for both new and existing users.
    - New users are created with terms automatically accepted
    - Existing users receive fresh tokens
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

@router.post("/refresh", response_model=schemas.Token)
async def refresh_access_token(
    request: schemas.RefreshTokenRequest, session: SessionDep
):
    """
    Refresh tokens using refresh token (Refresh Token Rotation).

    Security: OAuth 2.0 BCP - implements refresh token rotation
    - Returns new access token AND new refresh token
    - Invalidates old refresh token immediately
    - Prevents refresh token reuse attacks
    """
    # Verify refresh token (checks expiration automatically)
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get user
    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if refresh token matches stored token (prevents reuse)
    if user.refresh_token != request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or already used",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Generate NEW tokens (rotation)
    new_access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))

    # Update stored refresh token (invalidate old one)
    await user_service.update_refresh_token(
        session=session, db_user=user, refresh_token=new_refresh_token
    )

    return schemas.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(request: schemas.LogoutRequest, session: SessionDep):
    """
    Logout user by invalidating refresh token.
    """
    # Verify refresh token
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Get user and clear refresh token
    user = await user_service.get_user_by_id(session=session, user_id=UUID(user_id))

    if user:
        await user_service.update_refresh_token(session=session, db_user=user, refresh_token="")

    return {"message": "Successfully logged out"}