"""결제 서비스 — PayApp 결제 시작 및 웹훅 처리."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import settings
from src.subscription.models import Subscription, SubscriptionPlan, SubscriptionType

from src.plans.models import Plan
from .models import PaymentRecord, SubscriptionEvent
from .payapp import cancel_rebill, register_rebill
from .plans import plan_key
from .schemas import PaymentHistoryItem, PaymentInitiateRequest, PaymentInitiateResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 이벤트 로깅 헬퍼
# ---------------------------------------------------------------------------

async def _log_event(
    session: AsyncSession,
    user_id: UUID,
    sub_type: SubscriptionType | str,
    event_type: str,
    *,
    plan: str | None = None,
    rebill_no: str | None = None,
    amount: int | None = None,
    payapp_response: str | None = None,
    notes: str | None = None,
) -> None:
    """subscription_events에 이벤트를 기록한다."""
    sub_type_str = sub_type.value if isinstance(sub_type, SubscriptionType) else sub_type
    event = SubscriptionEvent(
        user_id=user_id,
        sub_type=sub_type_str,
        event_type=event_type,
        plan=plan,
        rebill_no=rebill_no,
        amount=amount,
        payapp_response=payapp_response,
        notes=notes,
    )
    session.add(event)


# ---------------------------------------------------------------------------
# 결제 내역 조회
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 결제 시작
# ---------------------------------------------------------------------------

async def initiate_payment(
    session: AsyncSession,
    user_id: UUID,
    req: PaymentInitiateRequest,
) -> PaymentInitiateResponse:
    """
    PayApp 정기결제 등록 URL을 반환한다.

    DB 저장 없음 — 결제 확인은 웹훅에서만 처리한다.
    var1=user_id, var2=plan_key 로 웹훅 매칭에 필요한 정보를 전달한다.
    자동갱신 중인 구독이 있으면 중복 결제를 차단한다.
    취소 예약(is_auto_renew=False) 상태는 재구독이 허용된다.
    """
    if not settings.PAYAPP_USERID or not settings.PAYAPP_LINKKEY:
        raise RuntimeError("PayApp credentials are not configured.")

    # 중복 결제 방지: 자동갱신 중인 구독이 이미 있으면 차단
    # is_auto_renew=False(취소 예약)는 PayApp 등록이 삭제된 상태이므로 재구독 허용
    now = datetime.now(timezone.utc)
    existing_sub = (await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == req.subscription_type,
            Subscription.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()

    if existing_sub and existing_sub.is_active:
        if existing_sub.is_auto_renew and (existing_sub.expires_at is None or existing_sub.expires_at > now):
            raise ValueError(
                f"이미 자동갱신 중인 {req.subscription_type.value} 구독이 있습니다. "
                f"만료일: {existing_sub.expires_at.strftime('%Y-%m-%d') if existing_sub.expires_at else '무기한'}"
            )
        if not existing_sub.is_auto_renew and existing_sub.expires_at and existing_sub.expires_at > now:
            raise ValueError(
                f"현재 구독이 {existing_sub.expires_at.strftime('%Y년 %m월 %d일')}에 종료됩니다. "
                "종료 후 재구독해주세요."
            )

    pkey = plan_key(req.subscription_type, req.plan)
    db_plan = (await session.execute(
        select(Plan).where(Plan.id == pkey, Plan.is_active == True)  # noqa: E712
    )).scalar_one_or_none()
    if db_plan is None:
        raise ValueError(f"지원하지 않는 플랜입니다: {pkey}")

    # 재구독 시 기존 만료일 기준으로 결제 주기일 설정
    cycle_day: int | None = None
    if existing_sub and existing_sub.expires_at and existing_sub.expires_at > now:
        cycle_day = existing_sub.expires_at.day

    try:
        result = await register_rebill(
            userid=settings.PAYAPP_USERID,
            linkkey=settings.PAYAPP_LINKKEY,
            good_name=db_plan.name,
            price=db_plan.price,
            user_id=str(user_id),
            plan_key=pkey,
            feedback_url=settings.PAYAPP_CALLBACK_URL,
            phone=req.phone,
            return_url=f"{settings.FRONTEND_URL}/payment/complete",
            cycle_day=cycle_day,
        )
    except Exception as e:
        logger.error("PayApp API 호출 오류: %s", e)
        raise RuntimeError(f"PayApp 연결 오류: {e}") from e

    if result.get("state") != "1":
        logger.error("PayApp rebillRegist 실패: %s", result)
        raise RuntimeError(
            f"PayApp 오류: {result.get('errorMessage') or result.get('errno', '알 수 없는 오류')}"
        )

    await _log_event(
        session, user_id, req.subscription_type, "INITIATED",
        plan=pkey,
        rebill_no=result.get("rebill_no"),
        amount=db_plan.price,
        payapp_response=str(result),
        notes="결제 페이지 요청",
    )
    await session.commit()

    logger.info(
        "결제 시작: user_id=%s plan=%s rebill_no=%s",
        user_id, plan_key(req.subscription_type, req.plan), result.get("rebill_no"),
    )
    return PaymentInitiateResponse(payurl=result["payurl"], rebill_no=result["rebill_no"])


# ---------------------------------------------------------------------------
# 구독 취소 (사용자 요청)
# ---------------------------------------------------------------------------

async def cancel_subscription(
    session: AsyncSession,
    user_id: UUID,
    sub_type: SubscriptionType,
) -> None:
    """
    구독 자동갱신을 해지한다.

    1. PayApp rebillDelete로 다음 달 자동결제를 중단한다.
       → PayApp 실패 시 RuntimeError를 발생시켜 DB를 업데이트하지 않는다.
    2. is_auto_renew=False로 표시해 만료 시 갱신하지 않음을 기록한다.
    3. 현재 결제 기간(expires_at)까지는 계속 사용 가능하다.
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

    # 가장 최근 결제 레코드에서 rebill_no 조회
    last_record = (await session.execute(
        select(PaymentRecord)
        .where(
            PaymentRecord.user_id == user_id,
            PaymentRecord.subscription_type == sub_type.value,
            PaymentRecord.paid_at.isnot(None),
        )
        .order_by(PaymentRecord.paid_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    rebill_no = last_record.rebill_no if last_record else None

    # PayApp 취소 요청
    if settings.PAYAPP_USERID and settings.PAYAPP_LINKKEY:
        if not rebill_no:
            logger.error(
                "취소 시도했으나 rebill_no 없음: user_id=%s type=%s last_record=%s",
                user_id, sub_type, last_record,
            )
            raise RuntimeError("결제 기록(rebill_no)을 찾을 수 없어 PayApp 취소를 진행할 수 없습니다.")

        logger.info("PayApp rebillDelete 요청: rebill_no=%s user_id=%s type=%s", rebill_no, user_id, sub_type)

        try:
            result = await cancel_rebill(
                userid=settings.PAYAPP_USERID,
                linkkey=settings.PAYAPP_LINKKEY,
                rebill_no=rebill_no,
            )
        except Exception as e:
            logger.error(
                "PayApp rebillDelete 네트워크 오류: rebill_no=%s user_id=%s error=%s",
                rebill_no, user_id, e,
            )
            await _log_event(
                session, user_id, sub_type, "CANCEL_PAYAPP_FAIL",
                plan=sub.plan.value if sub.plan else None,
                rebill_no=rebill_no,
                notes=f"네트워크 오류: {e}",
            )
            await session.commit()
            raise RuntimeError(f"PayApp 연결 오류: {e}") from e

        if result.get("state") != "1":
            errno = result.get("errno", "")
            errmsg = result.get("errorMessage", "알 수 없는 오류")
            logger.error(
                "PayApp rebillDelete 실패: rebill_no=%s errno=%s message=%s response=%s",
                rebill_no, errno, errmsg, result,
            )
            await _log_event(
                session, user_id, sub_type, "CANCEL_PAYAPP_FAIL",
                plan=sub.plan.value if sub.plan else None,
                rebill_no=rebill_no,
                payapp_response=str(result),
                notes=f"errno={errno}: {errmsg}",
            )
            await session.commit()
            raise RuntimeError(f"PayApp 정기결제 취소 실패 (errno={errno}): {errmsg}")

        logger.info("PayApp rebillDelete 성공: rebill_no=%s result=%s", rebill_no, result)
        await _log_event(
            session, user_id, sub_type, "CANCEL_PAYAPP_OK",
            plan=sub.plan.value if sub.plan else None,
            rebill_no=rebill_no,
            payapp_response=str(result),
        )
    else:
        # 로컬 개발 환경 (PayApp 미설정)
        logger.warning("PayApp 미설정 — DB만 취소 예약: user_id=%s type=%s", user_id, sub_type)

    # DB 업데이트 + 최종 이벤트 로그
    sub.is_auto_renew = False
    session.add(sub)

    await _log_event(
        session, user_id, sub_type, "CANCELLED",
        plan=sub.plan.value if sub.plan else None,
        rebill_no=rebill_no,
        notes=f"사용자 취소 요청. 만료일: {sub.expires_at.strftime('%Y-%m-%d') if sub.expires_at else '없음'}",
    )
    await session.commit()
    logger.info("구독 취소 완료: user_id=%s type=%s expires_at=%s", user_id, sub_type, sub.expires_at)


# ---------------------------------------------------------------------------
# 구독 즉시 비활성화 (관리자 전용)
# ---------------------------------------------------------------------------

async def admin_deactivate_subscription(
    session: AsyncSession,
    user_id: UUID,
    sub_type: SubscriptionType,
    admin_notes: str = "관리자 직접 비활성화",
) -> None:
    """
    관리자가 구독을 즉시 비활성화한다.

    1. PayApp rebillDelete 호출 (실패 시에도 DB는 업데이트)
    2. is_active=False, is_auto_renew=False
    3. MCP 토큰 무효화
    """
    sub = (await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.sub_type == sub_type,
        )
    )).scalar_one_or_none()

    if sub is None:
        raise ValueError(f"{sub_type.value} 구독이 없습니다.")

    # 가장 최근 결제 레코드에서 rebill_no 조회
    last_record = (await session.execute(
        select(PaymentRecord)
        .where(
            PaymentRecord.user_id == user_id,
            PaymentRecord.subscription_type == sub_type.value,
            PaymentRecord.paid_at.isnot(None),
        )
        .order_by(PaymentRecord.paid_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    rebill_no = last_record.rebill_no if last_record else None
    payapp_result_str: str | None = None

    # PayApp 취소 시도 (관리자 비활성화는 PayApp 실패해도 DB 업데이트)
    if settings.PAYAPP_USERID and settings.PAYAPP_LINKKEY and rebill_no:
        logger.info("관리자 비활성화 — PayApp rebillDelete 요청: rebill_no=%s user_id=%s", rebill_no, user_id)
        try:
            result = await cancel_rebill(
                userid=settings.PAYAPP_USERID,
                linkkey=settings.PAYAPP_LINKKEY,
                rebill_no=rebill_no,
            )
            payapp_result_str = str(result)
            if result.get("state") != "1":
                logger.error(
                    "관리자 비활성화 — PayApp rebillDelete 실패 (DB는 업데이트): rebill_no=%s result=%s",
                    rebill_no, result,
                )
                await _log_event(
                    session, user_id, sub_type, "CANCEL_PAYAPP_FAIL",
                    rebill_no=rebill_no,
                    payapp_response=payapp_result_str,
                    notes=f"관리자 비활성화 중 PayApp 실패. {admin_notes}",
                )
            else:
                logger.info("관리자 비활성화 — PayApp 취소 성공: rebill_no=%s", rebill_no)
                await _log_event(
                    session, user_id, sub_type, "CANCEL_PAYAPP_OK",
                    rebill_no=rebill_no,
                    payapp_response=payapp_result_str,
                )
        except Exception as e:
            logger.error("관리자 비활성화 — PayApp 오류 (DB는 업데이트): rebill_no=%s error=%s", rebill_no, e)
            await _log_event(
                session, user_id, sub_type, "CANCEL_PAYAPP_FAIL",
                rebill_no=rebill_no,
                notes=f"네트워크 오류: {e}. {admin_notes}",
            )
    else:
        logger.warning(
            "관리자 비활성화 — PayApp 스킵 (설정 없음 또는 rebill_no 없음): user_id=%s type=%s",
            user_id, sub_type,
        )

    # DB 즉시 비활성화
    sub.is_active = False
    sub.is_auto_renew = False
    if sub_type == SubscriptionType.MCP:
        sub.token = None
    session.add(sub)

    await _log_event(
        session, user_id, sub_type, "DEACTIVATED",
        plan=sub.plan.value if sub.plan else None,
        rebill_no=rebill_no,
        notes=admin_notes,
    )
    await session.commit()
    logger.info("구독 즉시 비활성화 완료: user_id=%s type=%s notes=%s", user_id, sub_type, admin_notes)


# ---------------------------------------------------------------------------
# 웹훅 처리
# ---------------------------------------------------------------------------

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

    logger.info(
        "PayApp 웹훅 수신: rebill_no=%s mul_no=%s pay_state=%s price=%s var1=%s var2=%s",
        rebill_no, mul_no, pay_state,
        form_data.get("price"), form_data.get("var1"), form_data.get("var2"),
    )

    if pay_state == 4:
        return await _handle_payment_complete(session, form_data, rebill_no, mul_no)
    elif pay_state in (8, 9, 32, 64):
        return await _handle_payment_cancel(session, form_data, rebill_no, pay_state, mul_no)
    else:
        logger.info("PayApp 웹훅: 처리 대상 아닌 pay_state=%s", pay_state)
        return "SUCCESS"


def _verify_webhook(form_data: dict[str, str]) -> bool:
    """PayApp 웹훅 인증 — userid·linkkey·linkval 단순 문자열 비교."""
    return (
        form_data.get("userid") == settings.PAYAPP_USERID
        and form_data.get("linkkey") == settings.PAYAPP_LINKKEY
        and form_data.get("linkval") == settings.PAYAPP_LINKVAL
    )


async def _handle_payment_complete(
    session: AsyncSession,
    form_data: dict[str, str],
    rebill_no: str,
    mul_no: str | None,
) -> str:
    """결제 완료 처리 — PaymentRecord 생성 + 구독 활성화 + 이벤트 로그."""

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
    db_plan = (await session.execute(
        select(Plan).where(Plan.id == plan_key_str)
    )).scalar_one_or_none()
    if db_plan is None:
        logger.error("웹훅 var2(plan_key) 알 수 없음: %s", plan_key_str)
        return "FAIL"

    # 금액 검증 (위변조 방지)
    webhook_price_str = form_data.get("price", "")
    if webhook_price_str and int(webhook_price_str) != db_plan.price:
        logger.warning(
            "웹훅 금액 불일치: expected=%d received=%s rebill_no=%s",
            db_plan.price, webhook_price_str, rebill_no,
        )
        return "FAIL"

    sub_type_str, plan_str = plan_key_str.split(":")
    now = datetime.now(timezone.utc)

    record = PaymentRecord(
        id=uuid4(),
        user_id=user_id,
        subscription_type=sub_type_str,
        plan=plan_str,
        amount=db_plan.price,
        rebill_no=rebill_no,
        mul_no=mul_no,
        pay_state=4,
        paid_at=now,
        card_name=form_data.get("card_name"),
        card_number=form_data.get("card_num"),
        receipt_url=form_data.get("csturl"),
        raw_webhook_data=str(form_data),
    )
    session.add(record)
    await _activate_subscription(session, record)

    sub_type = SubscriptionType(sub_type_str)
    await _log_event(
        session, user_id, sub_type, "ACTIVATED",
        plan=plan_str,
        rebill_no=rebill_no,
        amount=plan_info.price,
        payapp_response=str({k: v for k, v in form_data.items() if k not in ("userid", "linkkey", "linkval")}),
        notes=f"결제 완료. mul_no={mul_no}",
    )
    await session.commit()

    logger.info("결제 완료 처리: user_id=%s plan=%s rebill_no=%s amount=%d", user_id, plan_key_str, rebill_no, db_plan.price)
    return "SUCCESS"


async def _handle_payment_cancel(
    session: AsyncSession,
    form_data: dict[str, str],
    rebill_no: str,
    pay_state: int,
    mul_no: str | None,
) -> str:
    """취소·환불 처리 — 기존 PaymentRecord 업데이트 + 구독 비활성화 + 이벤트 로그."""

    pay_state_labels = {8: "취소", 9: "환불", 32: "취소", 64: "환불"}
    label = pay_state_labels.get(pay_state, f"pay_state={pay_state}")

    record = (await session.execute(
        select(PaymentRecord).where(PaymentRecord.rebill_no == rebill_no)
    )).scalar_one_or_none()

    user_id: UUID | None = None
    sub_type_str: str | None = None

    if record is not None:
        record.pay_state = pay_state
        record.raw_webhook_data = str(form_data)
        session.add(record)
        user_id = record.user_id
        sub_type_str = record.subscription_type
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

    if user_id and sub_type_str:
        await _log_event(
            session, user_id, SubscriptionType(sub_type_str), "DEACTIVATED",
            rebill_no=rebill_no,
            payapp_response=str({k: v for k, v in form_data.items() if k not in ("userid", "linkkey", "linkval")}),
            notes=f"PayApp 웹훅 {label}. pay_state={pay_state}",
        )

    await session.commit()
    logger.info("취소·환불 처리 완료: rebill_no=%s pay_state=%s(%s)", rebill_no, pay_state, label)
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

    stmt = select(Subscription).where(
        Subscription.user_id == record.user_id,
        Subscription.sub_type == sub_type,
    )
    sub = (await session.execute(stmt)).scalar_one_or_none()

    expires = now + timedelta(days=31)

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

    record.subscription_started_at = now
    record.subscription_expires_at = expires

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
