"""사용자 API 엔드포인트"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.common.responses import RESPONSES_CRUD_WITH_AUTH
from src.users import schemas, service
from src.users.dependencies import ActiveUser, SessionDep
from src.users.referral import apply_referral_code, get_referral_stats

router = APIRouter()


class ReferralInfoResponse(BaseModel):
    code: str
    invited_count: int


class ApplyReferralRequest(BaseModel):
    code: str


@router.get("/referral", response_model=ReferralInfoResponse)
async def get_my_referral(current_user: ActiveUser, session: SessionDep):
    """내 초대 코드 및 초대 현황 조회."""
    stats = await get_referral_stats(session, current_user)
    await session.commit()
    return ReferralInfoResponse(**stats)


@router.post("/referral/apply", status_code=status.HTTP_200_OK)
async def apply_referral(
    body: ApplyReferralRequest,
    current_user: ActiveUser,
    session: SessionDep,
):
    """초대 코드 입력 (양쪽 +10토큰)."""
    result = await apply_referral_code(session, current_user, body.code)
    if not result["success"]:
        await session.rollback()
        reason = result["reason"]
        if reason == "already_referred":
            raise HTTPException(status_code=409, detail="이미 초대 코드를 사용했습니다.")
        if reason == "invalid_code":
            raise HTTPException(status_code=404, detail="유효하지 않은 초대 코드입니다.")
        if reason == "self_referral":
            raise HTTPException(status_code=400, detail="자신의 초대 코드는 사용할 수 없습니다.")
    await session.commit()
    return {"message": "초대 코드 적용 완료"}


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

