import json
from typing import AsyncGenerator, List
from uuid import UUID

from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import Chat, ChatRole
from .schemas import ChatHistoryResponse, ChatHistoryItem, UpdateAnswerResponse
from .llm_service import generate_ai_response_stream, classify_draft_intent
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
        role=ChatRole.user,
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
    is_draft: bool,
    experience_ids: List[str] | None = None
) -> Chat:
    """AI 메시지 생성"""

    ai_msg = Chat(
        question_id=question.id,
        project_id=question.project_id,
        user_id=question.user_id,
        role=ChatRole.ai,
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


async def send_chat_stream(
    db: AsyncSession,
    qdrant_client: QdrantClient,
    *,
    question_id: UUID,
    content: str,
    experience_ids: list[str] | None = None,
    user_id: UUID,
) -> AsyncGenerator[str, None]:
    """메시지 전송 및 AI 응답 스트리밍"""

    # 1. Question 조회
    question = await get_question_by_id(db, question_id)
    if not question or question.user_id != user_id:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Question not found'}, ensure_ascii=False)}\n\n"
        return

    # 2. Project 조회
    project_stmt = select(Project).where(Project.id == question.project_id)
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()
    if not project:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Project not found'}, ensure_ascii=False)}\n\n"
        return

    # 3. 초안 여부 판단 (Function Calling) - 사용자 메시지 저장 전에 먼저 판단
    is_draft = await classify_draft_intent(content)

    # 4. 사용자 메시지 저장
    await create_user_chat(
        db=db,
        question=question,
        content=content,
        experience_ids=experience_ids,
    )

    # 5. AI 응답 스트리밍 (RunnableWithMessageHistory가 DB에서 히스토리 자동 로드)
    full_content = ""
    async for chunk_json in generate_ai_response_stream(
        db=db,
        question_id=question_id,
        user_message=content,
        question_content=question.question,
        max_length=question.max_length,
        company=project.company,
        recruit_notice=project.recruit_notice,
        experience_ids=experience_ids,
        qdrant_client=qdrant_client,
        user_id=str(user_id),
    ):
        chunk_data = json.loads(chunk_json)

        if chunk_data["type"] == "content":
            full_content += chunk_data["content"]
            yield f"data: {chunk_json}\n\n"

        elif chunk_data["type"] == "done":
            # 6. AI 메시지 저장
            ai_chat = await create_assistant_chat(
                db=db,
                question=question,
                content=full_content,
                is_draft=is_draft,
                experience_ids=experience_ids,
            )

            # 7. 완료 이벤트 전송
            done_data = json.dumps({
                "type": "done",
                "chat_id": str(ai_chat.id),
                "is_draft": is_draft
            }, ensure_ascii=False)
            yield f"data: {done_data}\n\n"

        elif chunk_data["type"] == "error":
            yield f"data: {chunk_json}\n\n"


async def get_chat_history_by_question(
    db: AsyncSession,
    question_id: UUID
) -> list[Chat]:
    """Question의 채팅 히스토리 조회"""
    stmt = select(Chat).where(Chat.question_id == question_id).order_by(Chat.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_chat_history_response(
    db: AsyncSession,
    question_id: UUID,
    user_id: UUID,
    cursor: str | None = None,
    size: int = 20
) -> ChatHistoryResponse | None:
    """채팅 히스토리 조회 (Cursor 기반 페이지네이션)"""

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

    # 3. ChatMessage 조회 (Cursor 기반 페이지네이션)
    # 최신 메시지부터 역순으로 조회 (채팅 UI 특성상)
    messages_stmt = select(Chat).where(Chat.question_id == question_id)

    if cursor:
        # cursor 이전의 메시지 조회 (cursor는 마지막으로 본 메시지 ID)
        cursor_chat_stmt = select(Chat.created_at).where(Chat.id == UUID(cursor))
        cursor_result = await db.execute(cursor_chat_stmt)
        cursor_created_at = cursor_result.scalar_one_or_none()

        if cursor_created_at:
            messages_stmt = messages_stmt.where(Chat.created_at < cursor_created_at)

    # size + 1로 조회해서 has_more 판단
    messages_stmt = messages_stmt.order_by(Chat.created_at.desc()).limit(size + 1)

    messages_result = await db.execute(messages_stmt)
    messages = list(messages_result.scalars().all())

    # has_more 판단 및 실제 반환할 메시지 제한
    has_more = len(messages) > size
    if has_more:
        messages = messages[:size]

    # 시간순 정렬 (역순으로 조회했으니 다시 정렬)
    messages = list(reversed(messages))

    # next_cursor 설정 (마지막 메시지의 ID)
    next_cursor = None
    if has_more and messages:
        next_cursor = str(messages[0].id)  # 가장 오래된 메시지 ID (역순이므로 첫 번째)

    # 4. 가장 최근 experience_ids 조회 (역순으로 찾기)
    latest_experience_ids = []
    for msg in reversed(messages):
        if msg.experience_ids:
            latest_experience_ids = msg.experience_ids
            break

    # 5. project_name 생성: "company_job"
    project_name = f"{project.company}_{project.job_position}"

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
        experience_ids=latest_experience_ids,
        next_cursor=next_cursor,
        has_more=has_more
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

    if chat.role != ChatRole.ai or not chat.is_draft:
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
