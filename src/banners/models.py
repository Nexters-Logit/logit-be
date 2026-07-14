"""배너 모델."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, Text
from sqlmodel import Field, SQLModel


class Banner(SQLModel, table=True):
    """홈 화면 배너. 어드민에서 관리 가능."""

    __tablename__ = "banners"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    image_url: str = Field(sa_column=Column(Text, nullable=False))
    link_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_visible: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    display_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
