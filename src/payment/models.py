"""결제 기록 모델."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlmodel import Field, SQLModel


class PaymentRecord(SQLModel, table=True):
    """PayApp 결제 이력."""

    __tablename__ = "payment_records"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    subscription_type: str = Field(sa_column=Column(String, nullable=False))
    plan: str = Field(sa_column=Column(String, nullable=False))
    amount: int = Field(sa_column=Column(Integer, nullable=False))

    # PayApp identifiers
    mul_no: str | None = Field(default=None, sa_column=Column(String, nullable=True, index=True))
    rebill_no: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Payment state: 4=완료, 8=취소, 9=환불, 32=취소, 64=환불
    pay_state: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))

    # 카드 정보 (PayApp webhook: card_name, card_num, csturl)
    card_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    card_number: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    receipt_url: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # 이 결제로 활성화된 구독 기간
    subscription_started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    subscription_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    raw_webhook_data: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    paid_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class SubscriptionEvent(SQLModel, table=True):
    """구독 이벤트 로그 — append-only 감사 테이블."""

    __tablename__ = "subscription_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)

    # logit | mcp
    sub_type: str = Field(sa_column=Column(String(20), nullable=False, index=True))

    # ACTIVATED | CANCEL_REQUESTED | CANCEL_PAYAPP_OK | CANCEL_PAYAPP_FAIL
    # CANCELLED | DEACTIVATED | WEBHOOK_RECEIVED | RENEWED
    event_type: str = Field(sa_column=Column(String(40), nullable=False))

    plan: str | None = Field(default=None, sa_column=Column(String(20), nullable=True))
    rebill_no: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    amount: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))

    # PayApp raw response (성공/실패 모두 저장)
    payapp_response: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # 추가 컨텍스트 (에러 메시지, 어드민 처리 등)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
