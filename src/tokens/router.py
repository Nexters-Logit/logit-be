"""토큰 API 라우터."""

from fastapi import APIRouter, HTTPException, status

from src.subscription.models import SubscriptionType
from src.subscription.service import get_active_subscription
from src.users.dependencies import ActiveUser, SessionDep

from .constants import ATTENDANCE_TOKENS, PLAN_MONTHLY_TOKENS
from .schemas import AttendanceResponse, TokenBalanceResponse
from .service import InsufficientTokensError, check_in, ensure_monthly_tokens, get_or_create_balance

router = APIRouter()


@router.get("/balance", response_model=TokenBalanceResponse)
async def get_token_balance(
    current_user: ActiveUser,
    session: SessionDep,
):
    """현재 토큰 잔액 및 플랜 정보 조회. 이번 결제 주기 토큰이 미지급이면 자동 지급한다."""
    subscription = await get_active_subscription(session, current_user.id, SubscriptionType.LOGIT)

    # 토큰 레코드 로드 후 월 지급 적용 (모두 세션 내에서 처리)
    token = await get_or_create_balance(session, current_user.id)
    await ensure_monthly_tokens(session, current_user.id, subscription)

    plan = "free"
    if subscription and subscription.is_active:
        plan = subscription.plan.value

    # commit 전에 인메모리 잔액 읽기 (commit 이후 재SELECT 방지)
    balance = token.balance
    await session.commit()

    return TokenBalanceResponse(
        balance=balance,
        plan=plan,
        monthly_tokens=PLAN_MONTHLY_TOKENS[plan],
    )


@router.post("/attendance", response_model=AttendanceResponse)
async def attendance_check_in(
    current_user: ActiveUser,
    session: SessionDep,
):
    """출석 체크인 (하루 1회, 이벤트 풀 소진 시 종료)."""
    try:
        token = await get_or_create_balance(session, current_user.id)
        success, message = await check_in(session, current_user.id)

        if not success:
            await session.rollback()
            if message == "already_checked_in":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="오늘 이미 출석했습니다.",
                )
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="출석 이벤트가 종료되었습니다.",
            )

        earned = ATTENDANCE_TOKENS
        new_balance = token.balance  # check_in이 credit을 호출해 token.balance가 갱신됨
        await session.commit()

        return AttendanceResponse(
            success=True,
            message="출석 완료",
            tokens_earned=earned,
            new_balance=new_balance,
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
