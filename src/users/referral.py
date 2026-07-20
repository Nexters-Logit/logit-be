"""친구 초대(Referral) 서비스."""

from __future__ import annotations

import logging
import secrets
import string

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.tokens.constants import REFERRAL_TOKENS
from src.tokens.models import TokenTransactionType
from src.tokens.service import credit, credit_referral_inviter

from .models import User

logger = logging.getLogger(__name__)

_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _generate_code() -> str:
    return "LOGIT-" + "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LENGTH))


async def get_or_create_referral_code(session: AsyncSession, user: User) -> str:
    """유저의 초대 코드를 반환하거나 생성한다."""
    if user.referral_code:
        return user.referral_code

    for _ in range(10):
        code = _generate_code()
        existing = await session.execute(
            select(User).where(User.referral_code == code)
        )
        if existing.scalar_one_or_none() is None:
            user.referral_code = code
            session.add(user)
            return code

    raise RuntimeError("초대 코드 생성 실패: 재시도 초과")


async def apply_referral_code(
    session: AsyncSession,
    invitee_user: User,
    code: str,
) -> dict:
    """
    초대 코드 적용.
    - 이미 초대받은 유저, 자기 자신 코드, 잘못된 코드 → 에러
    - 성공 시 양쪽 각 +10토큰
    """
    if invitee_user.referred_by_user_id:
        return {"success": False, "reason": "already_referred"}

    result = await session.execute(
        select(User).where(User.referral_code == code.upper().strip())
    )
    inviter = result.scalar_one_or_none()

    if inviter is None:
        return {"success": False, "reason": "invalid_code"}

    if inviter.id == invitee_user.id:
        return {"success": False, "reason": "self_referral"}

    try:
        # 위의 in-memory 체크만으로는 동시 요청(더블 탭/재시도)이 둘 다 통과해
        # 토큰이 이중 지급될 수 있다. "아직 초대받지 않은 경우에만" 원자적으로
        # claim하고, 영향받은 row 수로 실제 승인 여부를 판단한다 — 두 요청이
        # 동시에 들어와도 하나만 rowcount=1을 받는다.
        claim_result = await session.execute(
            update(User)
            .where(User.id == invitee_user.id, User.referred_by_user_id.is_(None))
            .values(referred_by_user_id=str(inviter.id))
        )
        if claim_result.rowcount == 0:
            # 동시 요청 중 하나가 이미 선점함 — rollback은 라우터가 일괄 처리한다
            # (invalid_code/self_referral과 동일하게).
            return {"success": False, "reason": "already_referred"}

        await credit_referral_inviter(session, inviter.id, REFERRAL_TOKENS)
        await credit(
            session, invitee_user.id, REFERRAL_TOKENS,
            TokenTransactionType.REFERRAL_INVITEE,
            f"초대 코드 입력 보상 (inviter:{inviter.id})",
        )
    except Exception:
        await session.rollback()
        logger.exception("Referral credit failed: inviter=%s invitee=%s", inviter.id, invitee_user.id)
        raise

    logger.info(
        "Referral applied: inviter=%s invitee=%s tokens=%d",
        inviter.id, invitee_user.id, REFERRAL_TOKENS,
    )
    return {"success": True, "inviter_id": str(inviter.id)}


async def get_referral_stats(session: AsyncSession, user: User) -> dict:
    """초대 현황 조회."""
    code = await get_or_create_referral_code(session, user)

    result = await session.execute(
        select(User).where(User.referred_by_user_id == str(user.id))
    )
    invited_users = result.scalars().all()

    return {
        "code": code,
        "invited_count": len(invited_users),
    }
