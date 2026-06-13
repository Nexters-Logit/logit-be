"""구독 서비스."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.security import create_mcp_token

from .models import Subscription, SubscriptionPlan, SubscriptionType


async def get_active_subscription(
    session: AsyncSession, user_id: UUID, type: SubscriptionType
) -> Subscription | None:
    """유저의 활성 구독을 반환한다. 없거나 만료되면 None."""
    now = datetime.now(timezone.utc)
    stmt = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.sub_type == type,
        Subscription.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    sub = result.scalar_one_or_none()

    if sub is None:
        return None

    # expires_at이 None이면 무기한
    if sub.expires_at is not None and sub.expires_at < now:
        return None

    return sub


async def get_all_subscriptions(
    session: AsyncSession, user_id: UUID
) -> list[Subscription]:
    """유저의 전체 구독 목록을 반환하고 만료된 구독은 is_active=False 처리한다."""
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subs = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    expired = [
        sub for sub in subs
        if sub.is_active and sub.expires_at is not None and sub.expires_at < now
    ]
    for sub in expired:
        sub.is_active = False
        session.add(sub)

    if expired:
        await session.commit()
        for sub in expired:
            await session.refresh(sub)

    return subs


async def get_subscription_by_type(
    session: AsyncSession, user_id: UUID, sub_type: SubscriptionType
) -> Subscription | None:
    """특정 타입의 구독을 반환하고 만료 여부를 동기화한다."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == sub_type,
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


async def get_or_create_mcp_token(
    session: AsyncSession, user_id: UUID
) -> tuple[str, bool]:
    """
    MCP 토큰을 반환한다. 유료 구독(BASIC)이 활성 상태일 때만 발급.

    Returns:
        (token, is_unavailable): 토큰 문자열과 사용 불가 여부.
        구독 없음·만료·미결제 → token="", is_unavailable=True.
    """
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == SubscriptionType.MCP,
        )
    )
    sub = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    # 구독 없음 또는 유료 플랜(BASIC)이 아닌 경우 거부
    if sub is None or sub.plan != SubscriptionPlan.BASIC:
        return "", True

    # 만료·비활성 체크
    if not sub.is_active or (sub.expires_at is not None and sub.expires_at < now):
        return "", True

    # 토큰이 없으면 발급 (구독 만료일 기준)
    if not sub.token:
        sub.token = create_mcp_token(subject=str(user_id), expires_at=sub.expires_at)
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

    return sub.token, False
