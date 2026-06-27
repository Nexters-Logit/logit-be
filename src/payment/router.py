"""결제 라우터."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_async_db
from src.subscription.models import SubscriptionType
from src.users.dependencies import CurrentUser

from . import service
from .schemas import PaymentHistoryItem, PaymentInitiateRequest, PaymentInitiateResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate_payment(
    req: PaymentInitiateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_async_db),
) -> PaymentInitiateResponse:
    """
    결제 시작 — PayApp 결제 페이지 URL을 반환한다.

    클라이언트는 반환된 `payurl`로 사용자를 리다이렉트하면 된다.
    결제 시 전화번호를 유저 프로필에 저장한다 (다음 결제 시 자동 사용).
    """
    try:
        result = await service.initiate_payment(session, current_user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        logger.error("결제 시작 오류: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    if current_user.phone != req.phone:
        current_user.phone = req.phone
        session.add(current_user)
        await session.commit()

    return result


@router.get("/history", response_model=list[PaymentHistoryItem])
async def get_payment_history(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_async_db),
) -> list[PaymentHistoryItem]:
    """
    결제 완료 내역을 최신순으로 반환한다.

    - 취소·환불된 건도 포함됩니다.
    - 결제 시도 중 실패한 건은 포함되지 않습니다.
    """
    return await service.get_payment_history(session, current_user.id)


@router.delete("/cancel/{sub_type}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_subscription(
    sub_type: SubscriptionType,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_async_db),
) -> None:
    """
    구독을 취소한다.

    - PayApp 정기결제 해지 + DB 구독 비활성화
    - 활성 구독이 없으면 404를 반환한다.
    """
    try:
        await service.cancel_subscription(session, current_user.id, sub_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error("구독 취소 오류: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.delete("/internal/subscriptions/{user_id}/{sub_type}", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
async def admin_deactivate_subscription(
    user_id: UUID,
    sub_type: SubscriptionType,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    """
    어드민 전용 — PayApp 취소 + 구독 즉시 비활성화.
    X-Admin-Secret 헤더 필수.
    """
    if not settings.ADMIN_SECRET or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        await service.admin_deactivate_subscription(session, user_id, sub_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error("어드민 구독 비활성화 오류: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_db),
) -> str:
    """
    PayApp 웹훅 수신 엔드포인트 (인증 불필요).

    PayApp이 결제 완료/취소/환불 이벤트를 URL-encoded form POST로 전송한다.
    검증 성공 시 "SUCCESS", 실패 시 "FAIL"을 반환한다.
    """
    form = await request.form()
    form_data = {k: str(v) for k, v in form.items()}
    logger.info("PayApp 웹훅 수신: mul_no=%s pay_state=%s", form_data.get("mul_no"), form_data.get("pay_state"))

    result = await service.handle_webhook(session, form_data)
    return result
