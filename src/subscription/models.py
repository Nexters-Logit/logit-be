"""구독 모델."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum as SAEnum, String, UniqueConstraint, text
from sqlmodel import Field, SQLModel


class SubscriptionType(str, Enum):
    MCP = "mcp"
    LOGIT = "logit"


class SubscriptionPlan(str, Enum):
    FREE_TRIAL = "free_trial"
    BASIC = "basic"
    PRO = "pro"


class Subscription(SQLModel, table=True):
    """구독 정보. 유저당 타입별로 하나."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "type", name="uq_subscription_user_type"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    sub_type: SubscriptionType = Field(
        sa_column=Column(
            "type",
            SAEnum(SubscriptionType, name="subscriptiontype", values_callable=lambda e: [x.value for x in e]),
            nullable=False,
        ),
    )
    is_active: bool = Field(default=True)
    plan: SubscriptionPlan = Field(
        default=SubscriptionPlan.BASIC,
        sa_column=Column(
            SAEnum(SubscriptionPlan, name="subscriptionplan", values_callable=lambda e: [x.value for x in e]),
            nullable=False,
            server_default=text("'basic'"),
        ),
    )

    token: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )

    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
