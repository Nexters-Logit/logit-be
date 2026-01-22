"""User dependencies for dependency injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_async_db
from src.security import verify_token
from src.users import service
from src.users.models import User

# OAuth2 scheme for token authentication
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_async_db)],
    token: Annotated[str, Depends(reusable_oauth2)],
) -> User:
    """
    Get current authenticated user from JWT token.

    FastAPI의 인증 방식 - Dependency Injection 사용.
    NestJS의 미들웨어와 달리, Depends()로 주입합니다.

    사용법:
        @router.get("/me")
        def get_me(current_user: CurrentUser):
            return current_user
    """
    # Verify and decode token
    user_id = verify_token(token, token_type="access")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = await service.get_user_by_id(session=session, user_id=UUID(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Check if token matches stored access token (invalidated tokens won't match)
    if user.access_token != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current active user.
    Additional layer to ensure user is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


# Type aliases for easier use in endpoints
SessionDep = Annotated[AsyncSession, Depends(get_async_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
