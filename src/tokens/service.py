"""토큰 시스템 핵심 서비스."""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.subscription.models import Subscription, SubscriptionPlan

from .constants import (
    ATTENDANCE_EVENT_TOTAL_POOL,
    ATTENDANCE_TOKENS,
    CHAT_TOKEN_COST,
    DRAFT_TOKEN_COST,
    PLAN_MONTHLY_TOKENS,
    SIGNUP_BONUS_TOKENS,
)
from .models import AttendanceLog, TokenTransaction, TokenTransactionType, UserToken

logger = logging.getLogger(__name__)


# ── 잔액 조회 / 생성 ──────────────────────────────────────────────

async def get_or_create_balance(session: AsyncSession, user_id: UUID) -> UserToken:
    """유저 토큰 레코드를 조회하거나 초기 생성한다."""
    uid = str(user_id)
    result = await session.execute(
        select(UserToken).where(UserToken.user_id == uid)
    )
    token = result.scalar_one_or_none()
    if token is None:
        token = UserToken(user_id=uid, balance=0)
        session.add(token)
        await session.flush()
    return token


async def get_balance(session: AsyncSession, user_id: UUID) -> int:
    """현재 토큰 잔액 반환 (월별 지급 없이 단순 조회)."""
    uid = str(user_id)
    result = await session.execute(
        select(UserToken.balance).where(UserToken.user_id == uid)
    )
    balance = result.scalar_one_or_none()
    return balance or 0


# ── 토큰 지급 / 차감 ──────────────────────────────────────────────

async def _record_transaction(
    session: AsyncSession,
    user_id: str,
    amount: int,
    tx_type: TokenTransactionType,
    description: str | None = None,
) -> None:
    session.add(TokenTransaction(
        user_id=user_id,
        amount=amount,
        type=tx_type,
        description=description,
    ))


async def credit(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    tx_type: TokenTransactionType,
    description: str | None = None,
) -> int:
    """토큰 지급. 새 잔액을 반환한다."""
    token = await get_or_create_balance(session, user_id)
    token.balance += amount
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(session, str(user_id), amount, tx_type, description)
    return token.balance


async def debit(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    tx_type: TokenTransactionType,
    description: str | None = None,
) -> int:
    """
    토큰 차감. 새 잔액을 반환한다.
    잔액 부족 시 InsufficientTokensError를 발생시킨다.
    """
    token = await get_or_create_balance(session, user_id)
    if token.balance < amount:
        raise InsufficientTokensError(current=token.balance, required=amount)
    token.balance -= amount
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(session, str(user_id), -amount, tx_type, description)
    return token.balance


# ── 월별 토큰 지급 ────────────────────────────────────────────────

def _current_billing_period_start(subscription: Subscription | None) -> datetime:
    """현재 결제 주기 시작 날짜 계산 (UTC 자정)."""
    now = datetime.now(timezone.utc)
    if subscription is None or not subscription.is_active:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    day = subscription.started_at.day
    last_day = calendar.monthrange(now.year, now.month)[1]
    anchor = min(day, last_day)
    period_start = now.replace(day=anchor, hour=0, minute=0, second=0, microsecond=0)

    if period_start > now:
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1
        last_day_prev = calendar.monthrange(prev_year, prev_month)[1]
        period_start = period_start.replace(
            year=prev_year,
            month=prev_month,
            day=min(day, last_day_prev),
        )
    return period_start


def _plan_key(subscription: Subscription | None) -> str:
    if subscription is None or not subscription.is_active:
        return "free"
    return subscription.plan.value  # "lite" | "pro"


async def ensure_monthly_tokens(
    session: AsyncSession,
    user_id: UUID,
    subscription: Subscription | None,
) -> tuple[bool, int]:
    """
    이번 결제 주기 토큰을 아직 지급하지 않았으면 지급한다.
    Returns (was_granted, amount_granted)
    """
    token = await get_or_create_balance(session, user_id)
    period_start = _current_billing_period_start(subscription)

    if token.last_monthly_grant_at is None:
        already_granted = False
    else:
        last_grant = token.last_monthly_grant_at
        if last_grant.tzinfo is None:
            last_grant = last_grant.replace(tzinfo=timezone.utc)
        already_granted = last_grant >= period_start
    if already_granted:
        return False, 0

    plan = _plan_key(subscription)
    amount = PLAN_MONTHLY_TOKENS[plan]

    token.balance += amount
    token.last_monthly_grant_at = datetime.now(timezone.utc)
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(
        session, str(user_id), amount, TokenTransactionType.MONTHLY_GRANT,
        f"{plan} 플랜 월 토큰 지급"
    )
    logger.info("Monthly tokens granted: user=%s plan=%s amount=%d", user_id, plan, amount)
    return True, amount


# ── 신규 가입 보너스 ──────────────────────────────────────────────

async def grant_signup_bonus(session: AsyncSession, user_id: UUID) -> int:
    """
    신규 가입 1회성 보너스 지급 (50토큰).
    이미 지급된 경우 건너뛴다. 새 잔액을 반환한다.
    """
    token = await get_or_create_balance(session, user_id)
    if token.signup_bonus_granted:
        return token.balance

    token.balance += SIGNUP_BONUS_TOKENS
    token.signup_bonus_granted = True
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(
        session, str(user_id), SIGNUP_BONUS_TOKENS,
        TokenTransactionType.SIGNUP_BONUS, "신규 가입 보너스"
    )
    logger.info("Signup bonus granted: user=%s amount=%d", user_id, SIGNUP_BONUS_TOKENS)
    return token.balance


# ── 출석 이벤트 ───────────────────────────────────────────────────

async def _attendance_event_remaining(session: AsyncSession) -> int:
    """출석 이벤트 잔여 풀 토큰 수 계산."""
    result = await session.execute(
        select(func.coalesce(func.sum(TokenTransaction.amount), 0)).where(
            TokenTransaction.type == TokenTransactionType.ATTENDANCE
        )
    )
    distributed = result.scalar_one()
    return max(0, ATTENDANCE_EVENT_TOTAL_POOL - distributed)


async def check_in(
    session: AsyncSession,
    user_id: UUID,
) -> tuple[bool, str]:
    """
    출석 체크인. 오늘 처음이고 이벤트 풀이 남아 있으면 3토큰 지급.
    Returns (success, message)
    """
    today = date.today()
    uid = str(user_id)

    existing = await session.execute(
        select(AttendanceLog).where(
            AttendanceLog.user_id == uid,
            AttendanceLog.date == today,
        )
    )
    if existing.scalar_one_or_none():
        return False, "already_checked_in"

    remaining_pool = await _attendance_event_remaining(session)
    if remaining_pool < ATTENDANCE_TOKENS:
        return False, "event_ended"

    session.add(AttendanceLog(user_id=uid, date=today))
    await credit(session, user_id, ATTENDANCE_TOKENS, TokenTransactionType.ATTENDANCE, "출석 이벤트")
    logger.info("Attendance check-in: user=%s tokens=%d", user_id, ATTENDANCE_TOKENS)
    return True, "success"


# ── 채팅 / 초안 토큰 차감 ────────────────────────────────────────

async def debit_chat(session: AsyncSession, user_id: UUID) -> int:
    """채팅 1회 토큰 차감 (-5). 새 잔액 반환."""
    return await debit(session, user_id, CHAT_TOKEN_COST, TokenTransactionType.CHAT_USAGE, "채팅")


async def debit_draft(session: AsyncSession, user_id: UUID) -> int:
    """초안 생성 토큰 차감 (-10). 새 잔액 반환."""
    return await debit(session, user_id, DRAFT_TOKEN_COST, TokenTransactionType.DRAFT_USAGE, "초안 생성")


# ── 예외 ──────────────────────────────────────────────────────────

class InsufficientTokensError(Exception):
    def __init__(self, current: int, required: int) -> None:
        self.current = current
        self.required = required
        super().__init__(f"토큰 부족: 필요 {required}, 보유 {current}")
