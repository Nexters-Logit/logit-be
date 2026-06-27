"""구독 API 엔드포인트."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.chats.dependencies import get_usage_limiter
from src.common.responses import (
    ERROR_403_FORBIDDEN,
    RESPONSES_CRUD_WITH_AUTH,
    create_responses,
)
from src.payment.plans import PLANS, plan_key as make_plan_key
from src.subscription.usage import UsageLimiter
from src.users.dependencies import ActiveUser, SessionDep

from .models import Subscription, SubscriptionType
from .schemas import PlanStatus, RemainingUsage, SubscriptionStatusResponse
from .service import (
    get_active_subscription,
    get_all_subscriptions,
    get_or_create_mcp_token,
    get_subscription_by_type,
)


class McpTokenResponse(BaseModel):
    token: str


router = APIRouter()


@router.get(
    "/me/status",
    response_model=SubscriptionStatusResponse,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="통합 구독 상태 조회",
)
async def get_subscription_status(
    session: SessionDep,
    current_user: ActiveUser,
    usage_limiter: UsageLimiter = Depends(get_usage_limiter),
):
    """
    현재 유저의 Logit + MCP 구독 상태와 남은 사용량을 한 번에 반환합니다.

    - 만료된 구독은 is_active=False로 반환합니다.
    - remaining: 이번 결제 주기의 남은 채팅/초안 횟수 (None=무제한).
    """
    logit_sub = await get_subscription_by_type(session, current_user.id, SubscriptionType.LOGIT)
    mcp_sub = await get_subscription_by_type(session, current_user.id, SubscriptionType.MCP)

    # 활성 Logit 구독 기준으로 남은 사용량 계산
    active_logit = await get_active_subscription(session, current_user.id, SubscriptionType.LOGIT)
    remaining_dict = await usage_limiter.get_remaining(current_user.id, active_logit)

    def _plan_status(sub: Subscription | None, sub_type: SubscriptionType) -> PlanStatus:
        if sub is None:
            return PlanStatus(
                subscription_type=sub_type,
                plan=None,
                is_active=False,
                is_auto_renew=False,
                started_at=None,
                expires_at=None,
                amount=None,
                next_payment_date=None,
            )
        amount: int | None = None
        if sub.plan is not None:
            plan_info = PLANS.get(make_plan_key(sub_type, sub.plan))
            if plan_info:
                amount = plan_info.price
        next_payment_date = sub.expires_at if (sub.is_active and sub.is_auto_renew) else None
        return PlanStatus(
            subscription_type=sub_type,
            plan=sub.plan,
            is_active=sub.is_active,
            is_auto_renew=sub.is_auto_renew,
            started_at=sub.started_at,
            expires_at=sub.expires_at,
            amount=amount,
            next_payment_date=next_payment_date,
        )

    return SubscriptionStatusResponse(
        logit=_plan_status(logit_sub, SubscriptionType.LOGIT),
        mcp=_plan_status(mcp_sub, SubscriptionType.MCP),
        remaining=RemainingUsage(
            chat=remaining_dict["chat"],
            draft=remaining_dict["draft"],
        ),
    )


@router.get(
    "/me",
    response_model=list[Subscription],
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="내 구독 상태 조회",
)
async def get_my_subscriptions(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    현재 유저의 전체 구독 목록을 반환합니다.

    - 만료된 구독은 자동으로 is_active=False 처리 후 반환합니다.
    """
    return await get_all_subscriptions(session, current_user.id)


@router.get(
    "/me/mcp-token",
    response_model=McpTokenResponse,
    responses=create_responses(
        RESPONSES_CRUD_WITH_AUTH,
        {403: ERROR_403_FORBIDDEN},
    ),
    summary="MCP 서버 토큰 발급",
)
async def get_mcp_token(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    활성 MCP 구독이 있는 유저에게 MCP 서버 접속용 JWT 토큰을 발급합니다.

    - 구독이 없거나 만료된 경우 403을 반환합니다.
    - 만료 여부는 호출 시점에 실시간으로 확인합니다.
    """
    token, is_expired = await get_or_create_mcp_token(session, current_user.id)

    if is_expired:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP 구독이 없거나 만료되었습니다. 결제 후 이용해주세요.",
        )

    return McpTokenResponse(token=token)


@router.get(
    "/me/{type}",
    response_model=Subscription | None,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="특정 타입 구독 상태 조회",
)
async def get_my_subscription_by_type(
    session: SessionDep,
    current_user: ActiveUser,
    type: SubscriptionType,
):
    """
    현재 유저의 특정 타입(mcp | logit) 구독을 반환합니다.

    - 만료 상태라면 is_active=False 로 업데이트 후 반환합니다.
    - 구독이 없으면 null을 반환합니다.
    """
    return await get_subscription_by_type(session, current_user.id, type)
