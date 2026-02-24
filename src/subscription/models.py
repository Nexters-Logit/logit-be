"""구독 모델."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class SubscriptionType(str, Enum):
    MCP = "mcp"
    LOGIT = "logit"


class Subscription(SQLModel, table=True):
    """구독 정보. 유저당 타입별로 하나."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "sub_type", name="uq_subscription_user_type"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    sub_type: SubscriptionType = Field(
        sa_column=Column("type", String(10), nullable=False),
        description="구독 타입 (mcp | logit)",
    )
    is_active: bool = Field(default=True)
    plan: str = Field(default="basic", max_length=50)

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
