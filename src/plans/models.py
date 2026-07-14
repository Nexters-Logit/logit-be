"""요금제 모델."""

from sqlalchemy import JSON, Boolean, Column, Integer, String, Text
from sqlmodel import Field, SQLModel


class Plan(SQLModel, table=True):
    """요금제 정보. 어드민에서 관리 가능."""

    __tablename__ = "plans"

    id: str = Field(
        sa_column=Column(String(50), primary_key=True),
        description="복합 키: {subscription_type}:{plan_key} (예: logit:lite)",
    )
    subscription_type: str = Field(
        sa_column=Column(String(20), nullable=False),
        description="logit | mcp",
    )
    plan_key: str = Field(
        sa_column=Column(String(20), nullable=False),
        description="lite | pro | basic",
    )
    name: str = Field(
        sa_column=Column(String(100), nullable=False),
    )
    original_price: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="정상가 (취소선 표시용)",
    )
    price: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="할인가 (실제 결제 금액)",
    )
    monthly_tokens: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
        description="이 플랜의 월 토큰 제공량",
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    badge: str | None = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
        description="배지 텍스트 (예: '가장 많이 선택해요')",
    )
    features: list | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="기능 목록 (JSON 배열)",
    )
    is_recommended: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    is_free: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    display_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    show_on_mobile: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
        description="모바일에서 노출 여부",
    )
