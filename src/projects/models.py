from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class ProjectBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = None
    is_active: bool = Field(default=True)


class Project(ProjectBase, table=True):
    __tablename__ = "projects"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # All datetimes are stored in UTC and include timezone info
    # PostgreSQL TIMESTAMP WITH TIME ZONE stores internally as UTC
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
