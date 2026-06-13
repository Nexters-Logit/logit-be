"""결제 기록 모델."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Integer, String
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

    raw_webhook_data: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    paid_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
