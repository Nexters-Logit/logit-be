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
    MCP 토큰을 반환한다.

    Returns:
        (token, is_expired): 토큰 문자열과 만료 여부.
        만료된 경우 token은 빈 문자열, is_expired=True.
    """
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == SubscriptionType.MCP,
        )
    )
    sub = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if sub is None:
        # 구독 이력 없음 → 무료 체험 발급 (최초 1회)
        sub = Subscription(
            user_id=user_id,
            sub_type=SubscriptionType.MCP,
            is_active=True,
            plan=SubscriptionPlan.FREE_TRIAL,
            started_at=now,
            expires_at=now + timedelta(days=30),
            token=create_mcp_token(subject=str(user_id)),
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return sub.token, False

    if not sub.is_active or (sub.expires_at is not None and sub.expires_at < now):
        return "", True

    if not sub.token:
        sub.token = create_mcp_token(subject=str(user_id))
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

    return sub.token, False
