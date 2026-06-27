"""구독 상태 응답 스키마."""

from datetime import datetime

from pydantic import BaseModel

from .models import SubscriptionPlan, SubscriptionType


class PlanStatus(BaseModel):
    subscription_type: SubscriptionType
    plan: SubscriptionPlan | None  # None = 구독 없음
    is_active: bool
    is_auto_renew: bool           # False = 취소 예약됨, 만료일까지만 사용 가능
    started_at: datetime | None
    expires_at: datetime | None
    amount: int | None            # 현재 플랜 월 결제 금액
    next_payment_date: datetime | None  # 다음 결제일 (취소 예약 시 None)


class RemainingUsage(BaseModel):
    chat: int | None   # None = 무제한
    draft: int | None  # None = 무제한


class SubscriptionStatusResponse(BaseModel):
    logit: PlanStatus
    mcp: PlanStatus
    remaining: RemainingUsage
