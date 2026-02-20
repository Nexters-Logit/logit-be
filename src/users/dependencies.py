"""User dependencies for dependency injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_async_db
from src.exceptions import AuthenticationError, InactiveUserError, UserNotFoundError
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
    user_id = verify_token(token, token_type="access")

    if user_id is None:
        raise AuthenticationError("Could not validate credentials")

    user = await service.get_user_by_id(session=session, user_id=UUID(user_id))

    if not user:
        raise UserNotFoundError()

    if not user.is_active:
        raise InactiveUserError()

    return user


# Type aliases for easier use in endpoints
SessionDep = Annotated[AsyncSession, Depends(get_async_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = CurrentUser
