from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from typing import List
from fastapi import HTTPException

from .models import Chat, ChatRole
from .schemas import ChatHistoryResponse, ChatHistoryItem, UpdateAnswerResponse
from src.questions.models import Question
from src.projects.models import Project


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
        role=ChatRole.AI,
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
    user_id: UUID,
) -> Chat:
    """메시지 전송 전체 플로우"""

    question = await get_question_by_id(db, question_id)
    if not question or question.user_id != user_id:
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


async def get_chat_history_response(
    db: AsyncSession,
    question_id: UUID,
    user_id: UUID
) -> ChatHistoryResponse | None:
    """채팅 히스토리 조회"""

    # 1. Question 조회
    question_stmt = select(Question).where(Question.id == question_id)
    question_result = await db.execute(question_stmt)
    question = question_result.scalar_one_or_none()

    if not question or question.user_id != user_id:
        return None
    
    # 2. Project 조회
    project_stmt = select(Project).where(Project.id == question.project_id)
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    if not project:
        return None

    # 3. ChatMessage 조회 (시간순 정렬)
    messages_stmt = select(Chat)\
        .where(Chat.question_id == question_id)\
        .order_by(Chat.created_at)

    messages_result = await db.execute(messages_stmt)
    messages = messages_result.scalars().all()

    # 4. 가장 최근 experience_ids 조회 (역순으로 찾기)
    latest_experience_ids = []
    for msg in reversed(messages):
        if msg.experience_ids:
            latest_experience_ids = msg.experience_ids
            break

    # 5. project_name 생성: "company_job"
    project_name = f"{project.company}_{project.employment_type}"  # todo: 이후에 job으로 수정

    # 6. created_at 포맷: "2026.01.20"
    created_at_str = project.created_at.strftime("%Y.%m.%d")

    # 7. 응답 생성
    return ChatHistoryResponse(
        project_name=project_name,
        created_at=created_at_str,
        question_id=question.id,
        question=question.question,
        chats=[
            ChatHistoryItem(
                id=msg.id,
                role=msg.role.value,
                content=msg.content,
                is_draft=msg.is_draft,
                created_at=msg.created_at
            )
            for msg in messages
        ],
        experience_ids=latest_experience_ids
    )


async def update_question_answer(
    db: AsyncSession,
    chat_id: UUID,
    user_id: UUID
) -> UpdateAnswerResponse | None:
    """AI 답변으로 자기소개서 답변 업데이트"""

    # 1. Chat 조회
    chat_stmt = select(Chat).where(Chat.id == chat_id)
    chat_result = await db.execute(chat_stmt)
    chat = chat_result.scalar_one_or_none()

    if not chat or chat.user_id != user_id:
        return None

    # 2. Question 조회 및 answer 업데이트
    question = await get_question_by_id(db, chat.question_id)
    if not question:
        return None

    question.answer = chat.content
    await db.commit()
    await db.refresh(question)

    return UpdateAnswerResponse(
        question_id=question.id,
        answer=question.answer
    )
