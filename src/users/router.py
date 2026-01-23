"""사용자 API 엔드포인트"""

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
)
async def get_current_user_info(current_user: ActiveUser):
    """
    현재 로그인한 사용자의 정보를 조회합니다.

    - Authorization 헤더의 JWT 토큰에서 사용자 정보를 추출합니다.
    """
    return current_user


@router.patch(
    "/me",
    response_model=schemas.UserPublic,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="현재 사용자 정보 수정",
)
async def update_current_user(
    session: SessionDep,
    current_user: ActiveUser,
    user_in: schemas.UserUpdate,
):
    """
    현재 로그인한 사용자의 정보를 수정합니다.

    - **user_in**: 수정할 필드 (부분 업데이트 지원)
    """
    user = await service.update_user(session=session, db_user=current_user, user_in=user_in)
    return user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="현재 사용자 계정 삭제",
)
async def delete_current_user(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    현재 로그인한 사용자의 계정을 삭제합니다.

    - is_active 플래그를 False로 설정하는 soft delete 방식으로 처리됩니다.
    """
    await service.delete_user(session=session, user_id=current_user.id)
    return None


@router.get(
    "/{user_id}",
    response_model=schemas.UserPublic,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="특정 사용자 정보 조회",
)
async def get_user_by_id(
    session: SessionDep,
    current_user: ActiveUser,
    user_id: UUID,
):
    """
    특정 사용자의 정보를 ID로 조회합니다.

    - **user_id**: 조회할 사용자의 UUID
    - 사용자를 찾을 수 없는 경우 404 에러를 반환합니다.
    """
    user = await service.get_user_by_id(session=session, user_id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user
