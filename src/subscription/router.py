"""구독 API 엔드포인트."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.common.responses import RESPONSES_CRUD_WITH_AUTH, ERROR_403_FORBIDDEN
from src.common.responses import create_responses
from src.security import create_mcp_token

from src.users.dependencies import ActiveUser, SessionDep

from .models import Subscription, SubscriptionPlan, SubscriptionType
from .service import get_active_subscription


class McpTokenResponse(BaseModel):
    token: str


router = APIRouter()


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
    from sqlmodel import select

    result = await session.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subs = result.scalars().all()

    now = datetime.now(timezone.utc)
    expired = []
    for sub in subs:
        if sub.is_active and sub.expires_at is not None and sub.expires_at < now:
            sub.is_active = False
            session.add(sub)
            expired.append(sub)

    if expired:
        await session.commit()
        for sub in expired:
            await session.refresh(sub)

    return subs


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
    from sqlmodel import select

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.sub_type == SubscriptionType.MCP,
        )
    )
    sub = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if sub is None:
        # 구독 이력 없음 → 무료 체험 발급 (최초 1회)
        sub = Subscription(
            user_id=current_user.id,
            sub_type=SubscriptionType.MCP,
            is_active=True,
            plan=SubscriptionPlan.FREE_TRIAL,
            started_at=now,
            expires_at=now + timedelta(days=30),
            token=create_mcp_token(subject=str(current_user.id)),
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return McpTokenResponse(token=sub.token)

    # 구독은 있지만 만료됨 → 결제 필요
    if not sub.is_active or (sub.expires_at is not None and sub.expires_at < now):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP 구독이 만료되었습니다. 결제 후 이용해주세요.",
        )

    # 활성 구독이지만 토큰 없음 (결제 등 다른 경로로 구독 생성된 경우)
    if not sub.token:
        sub.token = create_mcp_token(subject=str(current_user.id))
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

    return McpTokenResponse(token=sub.token)


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
    from sqlmodel import select

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.sub_type == type,
        )
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        return None

    now = datetime.now(timezone.utc)
    if sub.is_active and sub.expires_at is not None and sub.expires_at < now:
        sub.is_active = False
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

    return sub
