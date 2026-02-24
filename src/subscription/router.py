"""구독 API 엔드포인트."""

from datetime import datetime, timezone

from fastapi import APIRouter

from src.common.responses import RESPONSES_CRUD_WITH_AUTH
from src.users.dependencies import ActiveUser, SessionDep

from .models import Subscription, SubscriptionType
from .service import get_active_subscription

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
