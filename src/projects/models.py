from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, Date, DateTime, Text
from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """Project (프로젝트) - 지원하는 채용 공고 정보"""

    __tablename__ = "projects"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    company: str = Field(max_length=255, description="회사명")
    job_position: str = Field(max_length=100, description="직무 (백엔드 개발자, 프론트엔드 개발자 등)")
    recruit_notice: str = Field(
        sa_column=Column(Text, nullable=False),
        description="채용공고 전체 내용",
    )
    due_date: date | None = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
        description="마감날짜",
    )

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
    )
