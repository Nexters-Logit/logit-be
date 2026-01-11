"""Authentication router - OAuth and JWT endpoints."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from src.auth import constants, schemas, service
from src.core import create_access_token, settings, verify_token
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


@router.get("/google/callback", response_model=schemas.Token)
async def google_callback(code: str, session: SessionDep):
    """
    Handle Google OAuth callback.
    Exchange authorization code for access token and create/login user.
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


@router.get("/apple")
async def apple_login():
    """
    Redirect to Apple OAuth login page.
    Initiates the OAuth flow with Apple.
    """
    if not settings.APPLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Apple OAuth not configured",
        )

    apple_auth_url = (
        f"{constants.APPLE_AUTH_URL}?"
        f"client_id={settings.APPLE_CLIENT_ID}&"
        f"redirect_uri={settings.APPLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"response_mode=form_post&"
        f"scope={constants.APPLE_SCOPES}"
    )

    return RedirectResponse(url=apple_auth_url)


@router.post("/apple/callback")
async def apple_callback(code: str, session: SessionDep):
    """
    Handle Apple OAuth callback.
    Note: Apple uses POST for callback (response_mode=form_post).
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Apple OAuth callback not fully implemented yet",
    )


@router.post("/refresh")
async def refresh_access_token(
    request: schemas.RefreshTokenRequest, session: SessionDep
):
    """
    Refresh access token using refresh token.
    Allows clients to get a new access token without re-authenticating.
    """
    # Verify refresh token
    user_id = verify_token(request.refresh_token, token_type="refresh")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Get user
    user = user_service.get_user_by_id(session=session, user_id=int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if refresh token matches stored token
    if user.refresh_token != request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Generate new access token
    new_access_token = create_access_token(subject=str(user.id))

    return {"access_token": new_access_token, "token_type": "bearer"}


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
    user = user_service.get_user_by_id(session=session, user_id=int(user_id))

    if user:
        user_service.update_refresh_token(session=session, db_user=user, refresh_token="")

    return {"message": "Successfully logged out"}
