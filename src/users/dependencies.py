"""User dependencies for dependency injection."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from src.config import settings
from src.database import engine
from src.security import verify_token
from src.users import service
from src.users.models import User

# OAuth2 scheme for token authentication
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    FastAPI의 Dependency Injection 패턴입니다.
    엔드포인트에서 session: SessionDep로 사용합니다.
    """
    with Session(engine) as session:
        yield session


def get_current_user(
    session: Annotated[Session, Depends(get_db)],
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
    user = service.get_user_by_id(session=session, user_id=int(user_id))

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

    return user


def get_current_active_user(
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
SessionDep = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
