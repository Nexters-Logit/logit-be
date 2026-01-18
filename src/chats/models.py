from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Column, DateTime, Integer
from sqlmodel import Field, SQLModel


class Chat(SQLModel, table=True):
    """Chat database model."""

    __tablename__ = "chats"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Foreign keys
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    company_id: UUID = Field(foreign_key="companies.id", index=True)

    # Fields
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
