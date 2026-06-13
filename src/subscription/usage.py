"""월별 채팅/초안 사용량 추적기."""

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis

from .models import Subscription, SubscriptionPlan


@dataclass(frozen=True)
class PlanLimits:
    chat: int | None   # None = unlimited
    draft: int | None  # None = unlimited


FREE_LIMITS = PlanLimits(chat=5, draft=1)

_PLAN_LIMITS: dict[str, PlanLimits] = {
    SubscriptionPlan.LITE.value: PlanLimits(chat=50, draft=10),
    SubscriptionPlan.PRO.value: PlanLimits(chat=None, draft=None),
}


def get_plan_limits(subscription: Subscription | None) -> PlanLimits:
    """구독 상태에 따른 플랜 한도 반환."""
    if subscription is None or not subscription.is_active:
        return FREE_LIMITS
    return _PLAN_LIMITS.get(subscription.plan.value, FREE_LIMITS)


def _billing_period_key(started_at: datetime | None) -> str:
    """
    현재 날짜가 속하는 결제 주기 시작일 (YYYY-MM-DD).

    - started_at=None: 당월 1일 (Free 유저, 캘린더 월 기준)
    - started_at=6/10, now=7/15 → "2025-07-10"
    - started_at=6/10, now=7/05 → "2025-06-10"
    """
    now = datetime.now(timezone.utc)

    if started_at is None:
        return now.strftime("%Y-%m-01")

    day = started_at.day
    last_day = calendar.monthrange(now.year, now.month)[1]
    anchor = min(day, last_day)
    period_start = now.replace(day=anchor, hour=0, minute=0, second=0, microsecond=0)

    if period_start > now:
        # 이번 달 결제일이 아직 안 됐으면 전달로
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1
        last_day_prev = calendar.monthrange(prev_year, prev_month)[1]
        period_start = period_start.replace(
            year=prev_year, month=prev_month, day=min(day, last_day_prev)
        )

    return period_start.strftime("%Y-%m-%d")


def _period_ttl(started_at: datetime | None) -> int:
    """현재 결제 주기 종료까지 남은 초."""
    now = datetime.now(timezone.utc)
    y, m, d = map(int, _billing_period_key(started_at).split("-"))

    next_month = m % 12 + 1
    next_year = y + (1 if m == 12 else 0)
    next_day = min(d, calendar.monthrange(next_year, next_month)[1])
    next_period = datetime(next_year, next_month, next_day, tzinfo=timezone.utc)

    return max(int((next_period - now).total_seconds()) + 1, 1)


class UsageLimiter:
    """채팅/초안 월별 사용량 추적기."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _started_at(subscription: Subscription | None) -> datetime | None:
        return subscription.started_at if (subscription and subscription.is_active) else None

    def _key(self, user_id: UUID, period: str, usage_type: str) -> str:
        return f"usage:{user_id}:{period}:{usage_type}"

    async def _count(self, user_id: UUID, started_at: datetime | None, usage_type: str) -> int:
        period = _billing_period_key(started_at)
        val = await self.redis.get(self._key(user_id, period, usage_type))
        return int(val) if val else 0

    async def _incr(self, user_id: UUID, started_at: datetime | None, usage_type: str) -> int:
        period = _billing_period_key(started_at)
        key = self._key(user_id, period, usage_type)
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, _period_ttl(started_at))
        return (await pipe.execute())[0]

    # ── Public API ────────────────────────────────────────────

    async def check_chat(
        self, user_id: UUID, subscription: Subscription | None
    ) -> tuple[bool, int | None]:
        """(허용 여부, 남은 횟수 | None=무제한)"""
        limits = get_plan_limits(subscription)
        if limits.chat is None:
            return True, None
        count = await self._count(user_id, self._started_at(subscription), "chat")
        remaining = limits.chat - count
        return remaining > 0, max(0, remaining)

    async def check_draft(
        self, user_id: UUID, subscription: Subscription | None
    ) -> tuple[bool, int | None]:
        """(허용 여부, 남은 초안 횟수 | None=무제한)"""
        limits = get_plan_limits(subscription)
        if limits.draft is None:
            return True, None
        count = await self._count(user_id, self._started_at(subscription), "draft")
        remaining = limits.draft - count
        return remaining > 0, max(0, remaining)

    async def increment_chat(
        self, user_id: UUID, subscription: Subscription | None
    ) -> int:
        limits = get_plan_limits(subscription)
        if limits.chat is None:
            return -1
        return await self._incr(user_id, self._started_at(subscription), "chat")

    async def increment_draft(
        self, user_id: UUID, subscription: Subscription | None
    ) -> int:
        limits = get_plan_limits(subscription)
        if limits.draft is None:
            return -1
        return await self._incr(user_id, self._started_at(subscription), "draft")

    async def get_remaining(
        self, user_id: UUID, subscription: Subscription | None
    ) -> dict[str, int | None]:
        """남은 채팅/초안 횟수. None = 무제한."""
        limits = get_plan_limits(subscription)
        started_at = self._started_at(subscription)

        chat_remaining: int | None = None
        draft_remaining: int | None = None

        if limits.chat is not None:
            count = await self._count(user_id, started_at, "chat")
            chat_remaining = max(0, limits.chat - count)

        if limits.draft is not None:
            count = await self._count(user_id, started_at, "draft")
            draft_remaining = max(0, limits.draft - count)

        return {"chat": chat_remaining, "draft": draft_remaining}
