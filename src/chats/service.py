import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.exceptions import ForbiddenError
from src.projects.models import Project
from src.questions.models import Question

from .llm_service import generate_ai_response_stream
from .models import Chat, ChatRole
from .rate_limit import ChatRateLimiter
from .schemas import ChatHistoryItem, ChatHistoryResponse

logger = logging.getLogger(__name__)


async def create_user_chat(
    db: AsyncSession,
    question: Question,
    content: str,
    experience_ids: list[str] | None = None
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
    experience_ids: list[str] | None = None
) -> Chat:
    """AI 메시지 생성"""

    ai_msg = Chat(
        question_id=question.id,
        project_id=question.project_id,
        user_id=question.user_id,
        role=ChatRole.assistant,
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

    statement = select(Question).where(
        Question.id == question_id,
        Question.deleted_at.is_(None),
    )
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
    rate_limiter: ChatRateLimiter | None = None,
    is_test_user: bool = False,
) -> AsyncGenerator[str, None]:
    """메시지 전송 및 AI 응답 스트리밍"""

    # 1. Question 조회
    question = await get_question_by_id(db, question_id)
    if not question:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Question not found'}, ensure_ascii=False)}\n\n"
        return
    if question.user_id != user_id:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Access to this resource is forbidden.'}, ensure_ascii=False)}\n\n"
        return

    # 2. Project 조회
    project_stmt = select(Project).where(Project.id == question.project_id)
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()
    if not project:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Project not found'}, ensure_ascii=False)}\n\n"
        return

    # 3. 사용자 메시지 저장
    await create_user_chat(
        db=db,
        question=question,
        content=content,
        experience_ids=experience_ids,
    )

    # 4. AI 응답 스트리밍 (RunnableWithMessageHistory가 DB에서 히스토리 자동 로드)
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

        if chunk_data["type"] == "ping":
            yield f"data: {chunk_json}\n\n"

        elif chunk_data["type"] == "content":
            full_content += chunk_data["content"]
            yield f"data: {chunk_json}\n\n"

        elif chunk_data["type"] == "done":
            # 5. is_draft는 llm_service 파이프라인 분기에서 결정됨
            is_draft = chunk_data.get("is_draft", False)

            # 6. AI 메시지 저장
            ai_chat = await create_assistant_chat(
                db=db,
                question=question,
                content=full_content,
                is_draft=is_draft,
                experience_ids=experience_ids,
            )

            # 7. 스트리밍 완료 후 채팅 횟수 증가 (테스트 유저는 면제)
            done_data = {
                "type": "done",
                "chat_id": str(ai_chat.id),
                "is_draft": is_draft,
            }
            if rate_limiter:
                if is_test_user:
                    done_data["remaining_chats"] = -1  # 무제한
                else:
                    await rate_limiter.increment(user_id)
                    remaining = await rate_limiter.get_remaining(user_id)
                    done_data["remaining_chats"] = remaining
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

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
    size: int = 20,
    remaining_chats: int = 0,
) -> ChatHistoryResponse | None:
    """채팅 히스토리 조회 (Cursor 기반 페이지네이션)"""

    # 1. Question 조회
    question_stmt = select(Question).where(Question.id == question_id)
    question_result = await db.execute(question_stmt)
    question = question_result.scalar_one_or_none()

    if not question:
        return None
    if question.user_id != user_id:
        raise ForbiddenError()

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
        try:
            cursor_uuid = UUID(cursor)
        except ValueError:
            # 잘못된 cursor 형식이면 무시하고 첫 페이지 반환
            cursor_uuid = None

        if cursor_uuid:
            cursor_chat_stmt = select(Chat.created_at).where(Chat.id == cursor_uuid)
            cursor_result = await db.execute(cursor_chat_stmt)
            cursor_created_at = cursor_result.scalar_one_or_none()

            if cursor_created_at:
                # 동일 타임스탬프의 메시지 누락 방지
                messages_stmt = messages_stmt.where(
                (Chat.created_at < cursor_created_at) |
                ((Chat.created_at == cursor_created_at) & (Chat.id < cursor_uuid))
                )

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

    # 6. created_at
    project_created_at = project.created_at

    # 7. 응답 생성
    return ChatHistoryResponse(
        project_name=project_name,
        project_created_at=project_created_at,
        question_id=question.id,
        question=question.question,
        answer=question.answer,
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
        has_more=has_more,
        remaining_chats=remaining_chats,
    )
