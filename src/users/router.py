"""User router - User management endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.common.responses import RESPONSES_CRUD_WITH_AUTH
from src.users import schemas, service
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.get(
    "/me",
    response_model=schemas.UserPublic,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="현재 사용자 정보 조회",
    description="인증된 현재 사용자의 프로필 정보를 조회합니다.",
)
async def get_current_user_info(current_user: ActiveUser):
    """
    Get the public profile information of the currently authenticated user.
    The user is resolved from the JWT token in the Authorization header.
    """
    return current_user


@router.patch(
    "/me",
    response_model=schemas.UserPublic,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="현재 사용자 정보 수정",
    description="현재 사용자의 프로필 정보(예: 닉네임)를 수정합니다.",
)
async def update_current_user(
    session: SessionDep,
    current_user: ActiveUser,
    user_in: schemas.UserUpdate,
):
    """
    Update the profile of the currently authenticated user.

    - **user_in**: Fields to update.
    """
    user = await service.update_user(session=session, db_user=current_user, user_in=user_in)
    return user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="현재 사용자 계정 삭제",
    description="현재 사용자의 계정을 삭제합니다. 이 작업은 soft delete로 처리됩니다.",
)
async def delete_current_user(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    "Delete" the current user's account by setting its is_active flag to False (soft delete).
    """
    await service.delete_user(session=session, user_id=current_user.id)
    return None


@router.get(
    "/{user_id}",
    response_model=schemas.UserPublic,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="특정 사용자 정보 조회",
    description="사용자 ID로 특정 사용자의 공개 프로필 정보를 조회합니다. (주의: 현재는 모든 인증된 사용자가 다른 사용자를 조회할 수 있습니다. 추후 권한 제어가 필요할 수 있습니다.)",
)
async def get_user_by_id(
    session: SessionDep,
    current_user: ActiveUser,  # Ensures the endpoint is protected
    user_id: UUID,
):
    """
    Get a user's public profile by their ID.

    - **user_id**: The UUID of the user to retrieve.
    """
    user = await service.get_user_by_id(session=session, user_id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user