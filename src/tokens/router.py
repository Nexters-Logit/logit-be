"""토큰 API 라우터."""

from fastapi import APIRouter

from src.subscription.models import SubscriptionType
from src.subscription.service import get_active_subscription
from src.users.dependencies import ActiveUser, SessionDep

from .constants import PLAN_MONTHLY_TOKENS
from .schemas import TokenBalanceResponse
from .service import claim_referral_notification, ensure_monthly_tokens

router = APIRouter()


@router.get("/balance", response_model=TokenBalanceResponse)
async def get_token_balance(
    current_user: ActiveUser,
    session: SessionDep,
):
    """현재 토큰 잔액 및 플랜 정보 조회. 이번 결제 주기 토큰이 미지급이면 자동 지급한다."""
    subscription = await get_active_subscription(session, current_user.id, SubscriptionType.LOGIT)

    was_granted, granted_amount, token = await ensure_monthly_tokens(session, current_user.id, subscription)
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
        referral_reward_received=referral_count > 0,
        referral_reward_amount=referral_amount,
        referral_reward_count=referral_count,
    )
