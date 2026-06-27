"""결제 요청/응답 스키마."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.subscription.models import SubscriptionPlan, SubscriptionType

_PHONE_RE = re.compile(r"^01[0-9]{8,9}$")


class PaymentInitiateRequest(BaseModel):
    subscription_type: SubscriptionType
    plan: SubscriptionPlan
    phone: str  # 구매자 전화번호 (PayApp recvphone 필수)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if not _PHONE_RE.match(digits):
            raise ValueError("올바른 휴대폰 번호를 입력해주세요. (예: 01012345678)")
        return digits

    @field_validator("plan")
    @classmethod
    def validate_plan_for_type(cls, plan: SubscriptionPlan, info: object) -> SubscriptionPlan:
        sub_type = getattr(info, "data", {}).get("subscription_type")
        if sub_type == SubscriptionType.MCP and plan != SubscriptionPlan.BASIC:
            raise ValueError("MCP 구독은 basic 플랜만 지원합니다.")
        if sub_type == SubscriptionType.LOGIT and plan not in (
            SubscriptionPlan.LITE,
            SubscriptionPlan.PRO,
        ):
            raise ValueError("Logit 구독은 lite 또는 pro 플랜만 지원합니다.")
        return plan


class PaymentInitiateResponse(BaseModel):
    payurl: str
    rebill_no: str


PAY_STATE_LABEL: dict[int, str] = {
    4: "결제완료",
    8: "취소",
    9: "환불",
    32: "취소",
    64: "환불",
}


class PaymentHistoryItem(BaseModel):
    id: UUID
    subscription_type: str
    plan: str
    amount: int
    pay_state: int | None
    pay_state_label: str | None
    paid_at: datetime | None
    created_at: datetime
    card_name: str | None
    card_number: str | None
    receipt_url: str | None
    subscription_started_at: datetime | None
    subscription_expires_at: datetime | None

    @classmethod
    def from_record(cls, record: object) -> "PaymentHistoryItem":
        return cls(
            id=record.id,
            subscription_type=record.subscription_type,
            plan=record.plan,
            amount=record.amount,
            pay_state=record.pay_state,
            pay_state_label=PAY_STATE_LABEL.get(record.pay_state) if record.pay_state else None,
            paid_at=record.paid_at,
            created_at=record.created_at,
            card_name=record.card_name,
            card_number=record.card_number,
            receipt_url=record.receipt_url,
            subscription_started_at=record.subscription_started_at,
            subscription_expires_at=record.subscription_expires_at,
        )
