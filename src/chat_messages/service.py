from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from typing import List
from fastapi import HTTPException

from .models import ChatMessage, ChatRole
from src.chats.models import Chat


async def create_user_message(
    db: AsyncSession,
    chat: Chat,
    content: str,
    experience_ids: List[str] | None = None
) -> ChatMessage:
    """사용자 메시지 생성"""

    user_msg = ChatMessage(
        chat_id=chat.id,
        project_id=chat.project_id,
        user_id=chat.user_id,
        role=ChatRole.USER,
        content=content,
        experience_ids=experience_ids
    )

    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    return user_msg


async def create_assistant_message(
    db: AsyncSession,
    chat: Chat,
    content: str,
    user_content: str,
    experience_ids: List[str] | None = None
) -> ChatMessage:
    """AI 메시지 생성"""

    # 초안 생성 의도 감지
    is_draft = detect_draft_intent(user_content)

    ai_msg = ChatMessage(
        chat_id=chat.id,
        project_id=chat.project_id,
        user_id=chat.user_id,
        role=ChatRole.ASSISTANT,
        content=content,
        experience_ids=experience_ids,
        is_draft=is_draft
    )

    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)

    return ai_msg


async def get_chat_by_id(db: AsyncSession, chat_id: UUID) -> Chat | None:
    """Chat 조회"""

    statement = select(Chat).where(Chat.id == chat_id)
    result = await db.execute(statement)
    return result.scalars().first()


# todo: 이후 고도화
def detect_draft_intent(content: str) -> bool:
    """초안 생성 의도 감지"""

    keywords = ["써줘", "생성", "초안", "작성해줘", "만들어줘"]
    content_lower = content.lower()

    return any(keyword in content_lower for keyword in keywords)

async def send_message_flow(
    db: AsyncSession,
    *,
    chat_id: UUID,
    content: str,
    experience_ids: list[str] | None = None,
) -> ChatMessage:
    """메시지 전송 전체 플로우"""

    chat = await get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # 사용자 메시지
    await create_user_message(
        db=db,
        chat=chat,
        content=content,
        experience_ids=experience_ids,
    )

    # AI 응답 (임시)
    ai_response = "테스트 응답입니다. RAG는 이후 구현"

    # AI 메시지
    ai_msg = await create_assistant_message(
        db=db,
        chat=chat,
        content=ai_response,
        user_content=content,
        experience_ids=experience_ids,
    )

    return ai_msg