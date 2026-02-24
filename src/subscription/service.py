"""구독 서비스."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import Subscription, SubscriptionType


async def get_active_subscription(
    session: AsyncSession, user_id: UUID, type: SubscriptionType
) -> Subscription | None:
    """유저의 활성 구독을 반환한다. 없거나 만료되면 None."""
    now = datetime.now(timezone.utc)
    stmt = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.type == type,
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
