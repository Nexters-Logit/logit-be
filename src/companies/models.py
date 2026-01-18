from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Column, DateTime, String
from sqlmodel import Field, SQLModel

# chat 테이블 때문에 임의 생성
class Company(SQLModel, table=True):
    """Company database model."""

    __tablename__ = "companies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=30, index=True)
    talents: list[str] | None = Field(
        default=None, sa_column=Column(ARRAY(String))
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
