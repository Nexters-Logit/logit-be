from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from src.auth import constants, schemas, service
from src.config import settings
from src.security import create_access_token, create_refresh_token, verify_token
from src.users import service as user_service
from src.users.dependencies import SessionDep
from src.users.models import Gender

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

    Returns different responses based on user status:
    - New user: onboarding_token (requires additional info)
    - Existing user (onboarding incomplete): onboarding_token
    - Existing user (onboarding complete): access_token + refresh_token
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
    user = await user_service.get_user_by_id(session=session, user_id=int(user_id))

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
    user = await user_service.get_user_by_id(session=session, user_id=int(user_id))

    if user:
        await user_service.update_refresh_token(session=session, db_user=user, refresh_token="")

    return {"message": "Successfully logged out"}


@router.post("/complete-signup", response_model=schemas.CompleteSignupResponse)
async def complete_signup(request: schemas.CompleteSignupRequest, session: SessionDep):
    """
    Complete user signup with additional information.

    New users must provide:
    - age
    - gender
    - terms agreement

    Returns full JWT tokens upon successful completion.
    """
    # Verify onboarding token
    user_id = verify_token(request.onboarding_token, token_type="onboarding")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired onboarding token",
        )

    # Get user
    user = await user_service.get_user_by_id(session=session, user_id=int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already completed
    if user.onboarding_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onboarding already completed",
        )

    # Validate terms agreement
    if not request.terms_agreed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terms agreement is required",
        )

    # Validate gender
    try:
        gender_enum = Gender(request.gender)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gender value. Must be one of: {', '.join([g.value for g in Gender])}",
        )

    # Update user with onboarding info
    user.age = request.age
    user.gender = gender_enum
    user.terms_agreed = True
    user.terms_agreed_at = datetime.now(timezone.utc)
    user.onboarding_completed = True
    user.is_active = True  # Activate user
    user.updated_at = datetime.now(timezone.utc)

    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Generate full JWT tokens
    access_token = create_access_token(subject=str(user.id))
    refresh_token_jwt = create_refresh_token(subject=str(user.id))

    # Store refresh token
    await user_service.update_refresh_token(
        session=session, db_user=user, refresh_token=refresh_token_jwt
    )

    return schemas.CompleteSignupResponse(
        access_token=access_token,
        refresh_token=refresh_token_jwt,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "age": user.age,
            "gender": user.gender.value if user.gender else None,
            "profile_image_url": user.profile_image_url,
        },
    )