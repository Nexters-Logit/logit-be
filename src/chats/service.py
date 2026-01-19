from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from typing import List
from fastapi import HTTPException

from .models import Chat, ChatRole
from src.questions.models import Question


async def create_user_chat(
    db: AsyncSession,
    question: Question,
    content: str,
    experience_ids: List[str] | None = None
) -> Chat:
    """사용자 메시지 생성"""

    user_msg = Chat(
        question_id=question.id,
        project_id=question.project_id,
        user_id=question.user_id,
        role=ChatRole.USER,
        content=content,
        experience_ids=experience_ids
    )

    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    return user_msg


async def create_assistant_chat(
    db: AsyncSession,
    question: Question,
    content: str,
    user_content: str,
    experience_ids: List[str] | None = None
) -> Chat:
    """AI 메시지 생성"""

    # 초안 생성 의도 감지
    is_draft = detect_draft_intent(user_content)

    ai_msg = Chat(
        question_id=question.id,
        project_id=question.project_id,
        user_id=question.user_id,
        role=ChatRole.ASSISTANT,
        content=content,
        experience_ids=experience_ids,
        is_draft=is_draft
    )

    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)

    return ai_msg


async def get_question_by_id(db: AsyncSession, question_id: UUID) -> Question | None:
    """Question 조회"""

    statement = select(Question).where(Question.id == question_id)
    result = await db.execute(statement)
    return result.scalars().first()


# todo: 이후 고도화
def detect_draft_intent(content: str) -> bool:
    """초안 생성 의도 감지"""

    keywords = ["써줘", "생성", "초안", "작성해줘", "만들어줘"]
    content_lower = content.lower()

    return any(keyword in content_lower for keyword in keywords)

async def send_chat_flow(
    db: AsyncSession,
    *,
    question_id: UUID,
    content: str,
    experience_ids: list[str] | None = None,
) -> Chat:
    """메시지 전송 전체 플로우"""

    question = await get_question_by_id(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # 사용자 메시지
    await create_user_chat(
        db=db,
        question=question,
        content=content,
        experience_ids=experience_ids,
    )

    # AI 응답 (임시)
    ai_response = "테스트 응답입니다. RAG는 이후 구현"

    # AI 메시지
    ai_msg = await create_assistant_chat(
        db=db,
        question=question,
        content=ai_response,
        user_content=content,
        experience_ids=experience_ids,
    )

    return ai_msg