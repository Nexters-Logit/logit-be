"""AI 사용 로그 모델."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlmodel import Field, SQLModel


class AIUsageLog(SQLModel, table=True):
    """
    AI API 호출 및 MCP tool 사용 로그.

    - logit (채팅/초안): input_tokens, output_tokens, model 기록
    - mcp (tool 호출): tokens 없음 (Claude Desktop이 AI 호출), endpoint로 tool명 기록
    """

    __tablename__ = "ai_usage_logs"

    __table_args__ = (
        # 유저별 시계열 조회 (유저 상세 + 일/주/월 통계)
        Index("ix_ai_usage_user_created", "user_id", "created_at"),
        # logit/mcp 분리 조회 + 기간 필터
        Index("ix_ai_usage_subtype_created", "subscription_type", "created_at"),
        # 요금제별 집계
        Index("ix_ai_usage_plan_created", "plan", "created_at"),
        # MCP tool별 드릴다운
        Index("ix_ai_usage_subtype_endpoint_created", "subscription_type", "endpoint", "created_at"),
        # 기간만으로 필터링하는 전체 대시보드 집계
        Index("ix_ai_usage_created", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(sa_column=Column(String(36).with_variant(String(36), "postgresql"), nullable=False))

    # logit | mcp
    subscription_type: str = Field(sa_column=Column(String(20), nullable=False))
    # lite | pro | basic | free
    plan: str = Field(sa_column=Column(String(20), nullable=False))

    # logit: chat | draft | classification
    # mcp:  draft_cover_letter | list_experiences | get_experience | write_cover_letter | improve_answer | ...
    endpoint: str = Field(sa_column=Column(String(50), nullable=False))

    # gpt-4o-mini | claude-sonnet-4-6 | None (MCP tool calls)
    model: str | None = Field(default=None, sa_column=Column(String(100), nullable=True))

    # None for MCP tool calls (AI call happens in Claude Desktop, not our server)
    input_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    output_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
