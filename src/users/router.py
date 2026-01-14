"""User router - User management endpoints."""

from fastapi import APIRouter, HTTPException, status

from src.users import schemas, service
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.get("/me", response_model=schemas.UserPublic)
async def get_current_user_info(current_user: ActiveUser):
    """
    Get current authenticated user's information.

    FastAPI의 Dependency Injection을 사용한 인증:
    'current_user: ActiveUser'가 자동으로:
    1. Authorization 헤더에서 JWT 토큰 추출
    2. 토큰 검증
    3. 데이터베이스에서 사용자 조회
    4. 활성 상태 확인
    5. User 객체 반환

    NestJS의 @CurrentUser() 데코레이터와 동일한 역할.
    """
    return current_user


@router.patch("/me", response_model=schemas.UserPublic)
async def update_current_user(
    session: SessionDep,
    current_user: ActiveUser,
    user_in: schemas.UserUpdate,
):
    """
    Update current user's information.
    """
    user = await service.update_user(session=session, db_user=current_user, user_in=user_in)
    return user


@router.delete("/me")
async def delete_current_user(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    Delete current user's account.
    """
    await service.delete_user(session=session, user_id=current_user.id)
    return {"message": "User successfully deleted"}


@router.get("/{user_id}", response_model=schemas.UserPublic)
async def get_user_by_id(
    session: SessionDep,
    current_user: ActiveUser,
    user_id: int,
):
    """
    Get user by ID.
    Requires authentication.
    """
    user = await service.get_user_by_id(session=session, user_id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user