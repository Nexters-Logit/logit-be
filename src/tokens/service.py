"""토큰 시스템 핵심 서비스."""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.subscription.models import Subscription, SubscriptionPlan

from .exceptions import InsufficientTokensError
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

async def get_or_create_balance(
    session: AsyncSession,
    user_id: UUID,
    with_lock: bool = False,
) -> UserToken:
    """유저 토큰 레코드를 조회하거나 초기 생성한다."""
    stmt = select(UserToken).where(UserToken.user_id == user_id)
    if with_lock:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    token = result.scalar_one_or_none()
    if token is None:
        token = UserToken(user_id=user_id, balance=0)
        session.add(token)
        await session.flush()
        await _record_transaction(session, user_id, 0, TokenTransactionType.BALANCE_INIT, "토큰 계정 생성")
        logger.info("Token account initialized: user=%s", user_id)
    return token


async def get_balance(session: AsyncSession, user_id: UUID) -> int:
    """현재 토큰 잔액 반환 (월별 지급 없이 단순 조회)."""
    result = await session.execute(
        select(UserToken.balance).where(UserToken.user_id == user_id)
    )
    balance = result.scalar_one_or_none()
    return balance or 0


# ── 토큰 지급 / 차감 ──────────────────────────────────────────────

async def _record_transaction(
    session: AsyncSession,
    user_id: UUID,
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
    token = await get_or_create_balance(session, user_id, with_lock=True)
    token.balance += amount
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(session, user_id, amount, tx_type, description)
    return token.balance


async def credit_referral_inviter(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    description: str | None = None,
) -> int:
    """
    친구 초대 성공 시 초대자에게 토큰 지급.
    초대자는 지급 시점에 접속해 있지 않으므로, 다음 잔액 조회 시 알려줄 수 있도록
    미확인 보상 금액/건수를 함께 누적해둔다 (claim_referral_notification 참고).
    """
    token = await get_or_create_balance(session, user_id, with_lock=True)
    token.balance += amount
    token.unnotified_referral_amount += amount
    token.unnotified_referral_count += 1
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(
        session, user_id, amount, TokenTransactionType.REFERRAL_INVITER,
        description or "친구 초대 보상",
    )
    return token.balance


async def claim_referral_notification(
    session: AsyncSession,
    user_id: UUID,
) -> tuple[int, int]:
    """
    미확인 친구 초대 보상을 조회 후 즉시 초기화한다 (조회 시 1회만 알림).
    Returns (amount, count)
    """
    token = await get_or_create_balance(session, user_id, with_lock=True)
    amount = token.unnotified_referral_amount
    count = token.unnotified_referral_count
    if amount or count:
        token.unnotified_referral_amount = 0
        token.unnotified_referral_count = 0
        token.updated_at = datetime.now(timezone.utc)
    return amount, count


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
    token = await get_or_create_balance(session, user_id, with_lock=True)
    if token.balance < amount:
        raise InsufficientTokensError(current=token.balance, required=amount)
    token.balance -= amount
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(session, user_id, -amount, tx_type, description)
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
) -> tuple[bool, int, UserToken]:
    """
    이번 결제 주기 토큰을 아직 지급하지 않았으면 지급한다.
    Returns (was_granted, amount_granted, token)
    """
    token = await get_or_create_balance(session, user_id, with_lock=True)
    period_start = _current_billing_period_start(subscription)

    if token.last_monthly_grant_at is None:
        already_granted = False
    else:
        last_grant = token.last_monthly_grant_at
        if last_grant.tzinfo is None:
            last_grant = last_grant.replace(tzinfo=timezone.utc)
        already_granted = last_grant >= period_start
    if already_granted:
        return False, 0, token

    plan = _plan_key(subscription)
    amount = PLAN_MONTHLY_TOKENS[plan]

    token.balance += amount
    token.last_monthly_grant_at = datetime.now(timezone.utc)
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(
        session, user_id, amount, TokenTransactionType.MONTHLY_GRANT,
        f"{plan} 플랜 월 토큰 지급"
    )
    logger.info("Monthly tokens granted: user=%s plan=%s amount=%d", user_id, plan, amount)
    return True, amount, token


# ── 신규 가입 보너스 ──────────────────────────────────────────────

async def grant_signup_bonus(session: AsyncSession, user_id: UUID) -> int:
    """
    신규 가입 1회성 보너스 지급 (50토큰).
    이미 지급된 경우 건너뛴다. (granted, amount) 튜플 반환.
    """
    token = await get_or_create_balance(session, user_id, with_lock=True)
    if token.signup_bonus_granted:
        return False, 0

    token.balance += SIGNUP_BONUS_TOKENS
    token.signup_bonus_granted = True
    token.updated_at = datetime.now(timezone.utc)
    await _record_transaction(
        session, user_id, SIGNUP_BONUS_TOKENS,
        TokenTransactionType.SIGNUP_BONUS, "신규 가입 보너스"
    )
    logger.info("Signup bonus granted: user=%s amount=%d", user_id, SIGNUP_BONUS_TOKENS)
    return True, SIGNUP_BONUS_TOKENS


# ── 출석 이벤트 ───────────────────────────────────────────────────

_ATTENDANCE_POOL_KEY = "attendance:pool_remaining"
_ATTENDANCE_ENDED_KEY = "attendance:event_ended"
_ATTENDANCE_KEY_TTL = 25 * 3600  # 하루 + 1시간 (키 이름에 날짜 포함이므로 정리용)


async def _init_pool_if_needed(redis: Redis, session: AsyncSession) -> int:
    """Redis pool 카운터가 없으면 DB에서 계산해 초기화한다."""
    cached = await redis.get(_ATTENDANCE_POOL_KEY)
    if cached is not None:
        return int(cached)

    result = await session.execute(
        select(func.coalesce(func.sum(TokenTransaction.amount), 0)).where(
            TokenTransaction.type == TokenTransactionType.ATTENDANCE
        )
    )
    distributed = result.scalar_one()
    remaining = max(0, ATTENDANCE_EVENT_TOTAL_POOL - distributed)
    await redis.set(_ATTENDANCE_POOL_KEY, remaining)
    if remaining < ATTENDANCE_TOKENS:
        await redis.set(_ATTENDANCE_ENDED_KEY, "1")
    logger.info("Attendance pool initialized from DB: remaining=%d", remaining)
    return remaining


async def check_in(
    session: AsyncSession,
    user_id: UUID,
    redis: Redis,
) -> tuple[bool, str]:
    """
    출석 체크인. 오늘 처음이고 이벤트 풀이 남아 있으면 3토큰 지급.
    Redis로 레이스 컨디션 방지 및 DB 조회 최소화.
    Returns (success, message)
    """
    today = datetime.now(timezone.utc).date()
    user_key = f"attendance:{user_id}:{today}"

    # 1. 이벤트 종료 플래그 확인 (DB 조회 없음)
    if await redis.exists(_ATTENDANCE_ENDED_KEY):
        return False, "event_ended"

    # 2. 오늘 체크인 여부 원자적 확인 (SET NX — 레이스 컨디션 방지)
    acquired = await redis.set(user_key, "1", nx=True, ex=_ATTENDANCE_KEY_TTL)
    if not acquired:
        return False, "already_checked_in"

    # 3. 풀 카운터 초기화 (없으면 DB에서 1회만)
    await _init_pool_if_needed(redis, session)

    # 4. 풀에서 원자적 차감
    new_remaining = await redis.decrby(_ATTENDANCE_POOL_KEY, ATTENDANCE_TOKENS)
    if new_remaining < 0:
        # 풀 소진 — 복원 후 종료 플래그 설정
        await redis.incrby(_ATTENDANCE_POOL_KEY, ATTENDANCE_TOKENS)
        await redis.set(_ATTENDANCE_ENDED_KEY, "1")
        await redis.delete(user_key)
        return False, "event_ended"

    # 5. DB 영구 기록 (실패 시 Redis 롤백)
    try:
        session.add(AttendanceLog(user_id=user_id, date=today))
        await credit(session, user_id, ATTENDANCE_TOKENS, TokenTransactionType.ATTENDANCE, "출석 이벤트")
        logger.info("Attendance check-in: user=%s tokens=%d pool_remaining=%d", user_id, ATTENDANCE_TOKENS, new_remaining)
    except Exception:
        await redis.incrby(_ATTENDANCE_POOL_KEY, ATTENDANCE_TOKENS)
        await redis.delete(user_key)
        raise

    return True, "success"


# ── 채팅 / 초안 토큰 차감 ────────────────────────────────────────

async def debit_chat(session: AsyncSession, user_id: UUID) -> int:
    """채팅 1회 토큰 차감 (-5). 새 잔액 반환."""
    return await debit(session, user_id, CHAT_TOKEN_COST, TokenTransactionType.CHAT_USAGE, "채팅")


async def debit_draft(session: AsyncSession, user_id: UUID) -> int:
    """초안 생성 토큰 차감 (-10). 새 잔액 반환."""
    return await debit(session, user_id, DRAFT_TOKEN_COST, TokenTransactionType.DRAFT_USAGE, "초안 생성")
