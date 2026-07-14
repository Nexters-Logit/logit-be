"""토큰 API 라우터."""

import logging

from fastapi import APIRouter

from src.database import get_redis
from src.subscription.models import SubscriptionType
from src.subscription.service import get_active_subscription
from src.users.dependencies import ActiveUser, SessionDep

from .constants import ATTENDANCE_TOKENS, PLAN_MONTHLY_TOKENS
from .schemas import TokenBalanceResponse
from .service import (
    check_in,
    claim_referral_notification,
    claim_signup_bonus_notification,
    ensure_monthly_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/balance", response_model=TokenBalanceResponse)
async def get_token_balance(
    current_user: ActiveUser,
    session: SessionDep,
):
    """
    현재 토큰 잔액 및 플랜 정보 조회.

    조회 시점에 아직 반영되지 않은 지급 건이 있으면 함께 처리한다:
    - 월간 지급: 이번 결제 주기 토큰이 미지급이면 자동 지급 (시간창 기반, 트리거 이벤트 없음)
    - 출석: 오늘 첫 조회면 자동 체크인 (시간창 기반, 트리거 이벤트 없음)
    - 가입 보너스 / 친구 초대 보상: 계정 생성·초대 성공 시점에 이미 지급된 건을
      최초 1회만 알려준다 (claim-and-clear).
    """
    subscription = await get_active_subscription(session, current_user.id, SubscriptionType.LOGIT)

    was_granted, granted_amount, token = await ensure_monthly_tokens(session, current_user.id, subscription)

    attendance_received = False
    try:
        redis = await get_redis()
        attendance_received, _ = await check_in(session, current_user.id, redis)
    except Exception:
        logger.exception("Attendance auto check-in failed: user=%s", current_user.id)

    signup_bonus_amount = await claim_signup_bonus_notification(session, current_user.id)
    referral_amount, referral_count = await claim_referral_notification(session, current_user.id)

    plan = "free"
    if subscription and subscription.is_active:
        plan = subscription.plan.value

    balance = token.balance
    await session.commit()

    return TokenBalanceResponse(
        balance=balance,
        plan=plan,
        monthly_tokens=PLAN_MONTHLY_TOKENS[plan],
        monthly_grant_received=was_granted,
        monthly_grant_amount=granted_amount,
        signup_bonus_received=signup_bonus_amount > 0,
        signup_bonus_amount=signup_bonus_amount,
        attendance_received=attendance_received,
        attendance_amount=ATTENDANCE_TOKENS if attendance_received else 0,
        referral_reward_received=referral_count > 0,
        referral_reward_amount=referral_amount,
        referral_reward_count=referral_count,
    )
