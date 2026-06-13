"""결제 서비스 — PayApp 결제 시작 및 웹훅 처리."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import settings
from src.subscription.models import Subscription, SubscriptionPlan, SubscriptionType

from .models import PaymentRecord
from .payapp import cancel_rebill, register_rebill
from .plans import PLANS, PlanInfo, get_plan, plan_key
from .schemas import PaymentHistoryItem, PaymentInitiateRequest, PaymentInitiateResponse

logger = logging.getLogger(__name__)


async def get_payment_history(
    session: AsyncSession,
    user_id: UUID,
) -> list[PaymentHistoryItem]:
    """유저의 결제 완료 내역을 최신순으로 반환한다."""
    records = (await session.execute(
        select(PaymentRecord)
        .where(
            PaymentRecord.user_id == user_id,
            PaymentRecord.paid_at.isnot(None),
        )
        .order_by(PaymentRecord.paid_at.desc())
    )).scalars().all()

    return [PaymentHistoryItem.from_record(r) for r in records]


async def initiate_payment(
    session: AsyncSession,
    user_id: UUID,
    req: PaymentInitiateRequest,
) -> PaymentInitiateResponse:
    """
    PayApp 정기결제 등록 URL을 반환한다.

    DB 저장 없음 — 결제 확인은 웹훅에서만 처리한다.
    var1=user_id, var2=plan_key 로 웹훅 매칭에 필요한 정보를 전달한다.
    이미 활성 구독이 있으면 중복 결제를 차단한다.
    """
    if not settings.PAYAPP_USERID or not settings.PAYAPP_LINKKEY:
        raise RuntimeError("PayApp credentials are not configured.")

    # 중복 결제 방지: 같은 타입의 활성 구독이 이미 있으면 차단
    now = datetime.now(timezone.utc)
    existing_sub = (await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == req.subscription_type,
            Subscription.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()

    if existing_sub and (existing_sub.expires_at is None or existing_sub.expires_at > now):
        raise ValueError(
            f"이미 활성화된 {req.subscription_type.value} 구독이 있습니다. "
            f"만료일: {existing_sub.expires_at.strftime('%Y-%m-%d') if existing_sub.expires_at else '무기한'}"
        )

    plan_info: PlanInfo | None = get_plan(req.subscription_type, req.plan)
    if plan_info is None:
        raise ValueError(f"지원하지 않는 플랜입니다: {req.subscription_type}:{req.plan}")

    try:
        result = await register_rebill(
            userid=settings.PAYAPP_USERID,
            linkkey=settings.PAYAPP_LINKKEY,
            good_name=plan_info.good_name,
            price=plan_info.price,
            user_id=str(user_id),
            plan_key=plan_key(req.subscription_type, req.plan),
            feedback_url=settings.PAYAPP_CALLBACK_URL,
            phone=req.phone,
        )
    except Exception as e:
        logger.error("PayApp API 호출 오류: %s", e)
        raise RuntimeError(f"PayApp 연결 오류: {e}") from e

    if result.get("state") != "1":
        logger.error("PayApp rebillRegist 실패: %s", result)
        raise RuntimeError(
            f"PayApp 오류: {result.get('errorMessage') or result.get('errno', '알 수 없는 오류')}"
        )

    return PaymentInitiateResponse(payurl=result["payurl"], rebill_no=result["rebill_no"])


async def cancel_subscription(
    session: AsyncSession,
    user_id: UUID,
    sub_type: SubscriptionType,
) -> None:
    """
    구독 자동갱신을 해지한다.

    - PayApp rebillDelete로 다음 달 자동결제를 중단한다.
    - 현재 결제 기간(expires_at)까지는 계속 사용 가능하다. (is_active 유지)
    - is_auto_renew=False로 표시해 만료 시 갱신하지 않음을 기록한다.
    - PayApp 호출이 실패해도 DB는 업데이트하고 예외를 기록한다.
    """
    sub = (await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == sub_type,
            Subscription.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()

    if sub is None:
        raise ValueError(f"활성화된 {sub_type.value} 구독이 없습니다.")

    if not sub.is_auto_renew:
        raise ValueError(f"이미 취소 예약된 구독입니다. 만료일: {sub.expires_at.strftime('%Y-%m-%d') if sub.expires_at else '없음'}")

    # 마지막 결제 레코드에서 rebill_no 조회
    last_record = (await session.execute(
        select(PaymentRecord)
        .where(
            PaymentRecord.user_id == user_id,
            PaymentRecord.subscription_type == sub_type.value,
        )
        .order_by(PaymentRecord.paid_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if last_record and last_record.rebill_no and settings.PAYAPP_USERID and settings.PAYAPP_LINKKEY:
        try:
            result = await cancel_rebill(
                userid=settings.PAYAPP_USERID,
                linkkey=settings.PAYAPP_LINKKEY,
                rebill_no=last_record.rebill_no,
            )
            if result.get("state") != "1":
                logger.warning(
                    "PayApp rebillDelete 실패 (DB는 취소 예약 처리): rebill_no=%s result=%s",
                    last_record.rebill_no, result,
                )
        except Exception as e:
            logger.error("PayApp rebillDelete 호출 오류 (DB는 취소 예약 처리): %s", e)
    else:
        logger.warning(
            "rebill_no 없음 또는 PayApp 미설정 — DB만 취소 예약: user_id=%s type=%s",
            user_id, sub_type,
        )

    # 즉시 비활성화하지 않고 만료일까지 사용 가능하도록 자동갱신만 해제
    sub.is_auto_renew = False
    session.add(sub)
    await session.commit()
    logger.info("구독 자동갱신 해지 완료: user_id=%s type=%s expires_at=%s", user_id, sub_type, sub.expires_at)


def _verify_webhook(form_data: dict[str, str]) -> bool:
    """PayApp 웹훅 인증 — userid·linkkey·linkval 단순 문자열 비교."""
    return (
        form_data.get("userid") == settings.PAYAPP_USERID
        and form_data.get("linkkey") == settings.PAYAPP_LINKKEY
        and form_data.get("linkval") == settings.PAYAPP_LINKVAL
    )


async def handle_webhook(
    session: AsyncSession,
    form_data: dict[str, str],
) -> str:
    """
    PayApp 웹훅 처리.

    결제 완료(pay_state=4) 시에만 PaymentRecord를 생성한다.
    취소·환불(8/9/32/64) 시에는 기존 레코드를 찾아 구독을 비활성화한다.

    Returns:
        "SUCCESS" or "FAIL"
    """
    if not settings.PAYAPP_USERID or not settings.PAYAPP_LINKKEY or not settings.PAYAPP_LINKVAL:
        logger.error("PayApp 인증 정보가 설정되지 않았습니다.")
        return "FAIL"

    if not _verify_webhook(form_data):
        logger.warning("PayApp 웹훅 검증 실패: %s", form_data)
        return "FAIL"

    rebill_no = form_data.get("rebill_no", "")
    pay_state = int(form_data.get("pay_state", "0"))
    mul_no = form_data.get("mul_no")

    logger.info("PayApp 웹훅 수신: rebill_no=%s pay_state=%s", rebill_no, pay_state)

    if pay_state == 4:
        return await _handle_payment_complete(session, form_data, rebill_no, mul_no)
    elif pay_state in (8, 9, 32, 64):
        return await _handle_payment_cancel(session, form_data, rebill_no, pay_state, mul_no)
    else:
        logger.info("PayApp 웹훅: 처리 대상 아닌 pay_state=%s", pay_state)
        return "SUCCESS"


async def _handle_payment_complete(
    session: AsyncSession,
    form_data: dict[str, str],
    rebill_no: str,
    mul_no: str | None,
) -> str:
    """결제 완료 처리 — PaymentRecord 생성 + 구독 활성화."""

    # 중복 웹훅 방지
    existing = (await session.execute(
        select(PaymentRecord).where(PaymentRecord.rebill_no == rebill_no)
    )).scalar_one_or_none()

    if existing and existing.paid_at is not None:
        logger.info("중복 웹훅 무시: rebill_no=%s", rebill_no)
        return "SUCCESS"

    # var1=user_id, var2=plan_key 파싱
    try:
        user_id = UUID(form_data.get("var1", ""))
    except ValueError:
        logger.error("웹훅 var1(user_id) 파싱 실패: %s", form_data.get("var1"))
        return "FAIL"

    plan_key_str = form_data.get("var2", "")
    plan_info = PLANS.get(plan_key_str)
    if plan_info is None:
        logger.error("웹훅 var2(plan_key) 알 수 없음: %s", plan_key_str)
        return "FAIL"

    # 금액 검증 (위변조 방지)
    webhook_price_str = form_data.get("price", "")
    if webhook_price_str and int(webhook_price_str) != plan_info.price:
        logger.warning(
            "웹훅 금액 불일치: expected=%d received=%s rebill_no=%s",
            plan_info.price, webhook_price_str, rebill_no,
        )
        return "FAIL"

    sub_type_str, plan_str = plan_key_str.split(":")
    now = datetime.now(timezone.utc)

    record = PaymentRecord(
        id=uuid4(),
        user_id=user_id,
        subscription_type=sub_type_str,
        plan=plan_str,
        amount=plan_info.price,
        rebill_no=rebill_no,
        mul_no=mul_no,
        pay_state=4,
        paid_at=now,
        raw_webhook_data=str(form_data),
    )
    session.add(record)
    await _activate_subscription(session, record)
    await session.commit()

    logger.info("결제 완료 처리: user_id=%s plan=%s", user_id, plan_key_str)
    return "SUCCESS"


async def _handle_payment_cancel(
    session: AsyncSession,
    form_data: dict[str, str],
    rebill_no: str,
    pay_state: int,
    mul_no: str | None,
) -> str:
    """취소·환불 처리 — 기존 PaymentRecord 업데이트 + 구독 비활성화."""

    record = (await session.execute(
        select(PaymentRecord).where(PaymentRecord.rebill_no == rebill_no)
    )).scalar_one_or_none()

    if record is not None:
        record.pay_state = pay_state
        record.raw_webhook_data = str(form_data)
        session.add(record)
        await _deactivate_subscription(session, record.user_id, SubscriptionType(record.subscription_type))
    else:
        # 결제 완료 이전 취소 — var1/var2로 구독만 비활성화
        try:
            user_id = UUID(form_data.get("var1", ""))
            sub_type_str = form_data.get("var2", "").split(":")[0]
            sub_type = SubscriptionType(sub_type_str)
        except (ValueError, IndexError):
            logger.error("취소 웹훅 파싱 실패: %s", form_data)
            return "FAIL"
        await _deactivate_subscription(session, user_id, sub_type)

    await session.commit()
    logger.info("취소·환불 처리 완료: rebill_no=%s pay_state=%s", rebill_no, pay_state)
    return "SUCCESS"


async def _activate_subscription(
    session: AsyncSession,
    record: PaymentRecord,
) -> None:
    """결제 완료 후 구독을 1개월 활성화한다. MCP는 즉시 토큰도 발급."""
    from src.security import create_mcp_token

    sub_type = SubscriptionType(record.subscription_type)
    plan = SubscriptionPlan(record.plan)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=31)

    stmt = select(Subscription).where(
        Subscription.user_id == record.user_id,
        Subscription.sub_type == sub_type,
    )
    sub = (await session.execute(stmt)).scalar_one_or_none()

    if sub is None:
        sub = Subscription(
            user_id=record.user_id,
            sub_type=sub_type,
            is_active=True,
            is_auto_renew=True,
            plan=plan,
            started_at=now,
            expires_at=expires,
        )
    else:
        sub.is_active = True
        sub.is_auto_renew = True
        sub.plan = plan
        sub.started_at = now
        sub.expires_at = expires

    if sub_type == SubscriptionType.MCP:
        sub.token = create_mcp_token(subject=str(record.user_id), expires_at=expires)

    session.add(sub)


async def _deactivate_subscription(
    session: AsyncSession,
    user_id: UUID,
    sub_type: SubscriptionType,
) -> None:
    """결제 취소·환불 웹훅 수신 시 구독을 즉시 비활성화한다."""
    sub = (await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == sub_type,
        )
    )).scalar_one_or_none()

    if sub is None:
        logger.warning("비활성화할 구독 없음: user_id=%s type=%s", user_id, sub_type)
        return

    sub.is_active = False
    sub.is_auto_renew = False
    if sub_type == SubscriptionType.MCP:
        sub.token = None

    session.add(sub)
    logger.info("구독 즉시 비활성화: user_id=%s type=%s", user_id, sub_type)
