from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


class Question(SQLModel, table=True):
    """Question (자기소개서) - 채용 공고 문항 및 답변"""

    __tablename__ = "questions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    question: str = Field(max_length=100, description="문항")  # 문항
    max_length: int | None = Field(default=None, description="글자수 제한")
    order: int = Field(default=1, description="문항 번호 (순서)")
    answer: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="자기소개서 답변",
    )
    is_completed: bool = Field(default=False, index=True, description="작성 완료 여부")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="삭제 시간 (Soft Delete)",
    )
