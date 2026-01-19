from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class ChatRole(str, Enum):
    """Chat message role types."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(SQLModel, table=True):
    """Chat message database model."""

    __tablename__ = "chat_messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Foreign key
    chat_id: UUID = Field(foreign_key="chats.id", index=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    # Fields
    role: ChatRole = Field(index=True)
    content: str
    experience_ids: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String)),    
        description="선택한 경험 ID 배열 (Qdrant에 저장된 경험, 최대 3개)"
    )
    is_draft: bool = Field(
        default=False,
        description="자소서 초안 여부 (True면 '자소서로 업데이트' 버튼 표시)"
    )
    is_selected: bool = Field(
        default=False,
        description="최종 선택된 자소서 여부 (final_answer에 반영됨)"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
