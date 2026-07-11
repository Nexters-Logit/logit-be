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
from src.tokens.constants import CHAT_TOKEN_COST, DRAFT_TOKEN_COST
from src.tokens.exceptions import InsufficientTokensError
from src.tokens.models import TokenTransactionType
from src.tokens.service import credit, debit

from .llm_service import generate_ai_response_stream
from .models import Chat, ChatRole
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

    # 3. 선차감 — 최대 비용(초안 10토큰) 기준, 테스트 유저 면제
    # is_draft는 스트리밍 끝에 확정되므로 보수적으로 최대 비용을 먼저 차감한다.
    prededucted_balance: int | None = None
    if not is_test_user:
        try:
            prededucted_balance = await debit(
                db, user_id, DRAFT_TOKEN_COST,
                TokenTransactionType.DRAFT_USAGE, "선차감 (채팅/초안)"
            )
            await db.commit()
        except InsufficientTokensError as e:
            done_data: dict = {
                "type": "done",
                "chat_id": None,
                "is_draft": False,
                "draft_limit_exceeded": False,
                "token_balance": e.current,
            }
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            return

    # 4. 사용자 메시지 저장 (토큰 차감 확정 후)
    await create_user_chat(
        db=db,
        question=question,
        content=content,
        experience_ids=experience_ids,
    )

    # 5. AI 응답 스트리밍
    full_content = ""
    try:
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
            usage_user_id=user_id,
        ):
            chunk_data = json.loads(chunk_json)

            if chunk_data["type"] == "ping":
                yield f"data: {chunk_json}\n\n"

            elif chunk_data["type"] == "content":
                full_content += chunk_data["content"]
                yield f"data: {chunk_json}\n\n"

            elif chunk_data["type"] == "done":
                is_draft = chunk_data.get("is_draft", False)
                actual_cost = DRAFT_TOKEN_COST if is_draft else CHAT_TOKEN_COST

                # 실제 비용 확정 후 차액 환불 (채팅이면 10 - 5 = 5토큰 환불)
                remaining_balance: int | None = None
                if not is_test_user:
                    refund_amount = DRAFT_TOKEN_COST - actual_cost
                    if refund_amount > 0:
                        remaining_balance = await credit(
                            db, user_id, refund_amount,
                            TokenTransactionType.CHAT_REFUND,
                            "채팅 비용 조정 (선차감 차액 환불)"
                        )
                    else:
                        remaining_balance = prededucted_balance  # 초안, 차액 없음

                # AI 메시지 저장 (환불 포함 한 번에 commit)
                ai_chat = await create_assistant_chat(
                    db=db,
                    question=question,
                    content=full_content,
                    is_draft=is_draft,
                    experience_ids=experience_ids,
                )

                done_data = {
                    "type": "done",
                    "chat_id": str(ai_chat.id),
                    "is_draft": is_draft,
                    "draft_limit_exceeded": False,
                    "token_balance": remaining_balance,
                    "tokens_used": 0 if is_test_user else actual_cost,
                }
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

            elif chunk_data["type"] == "error":
                # llm_service가 내부에서 예외를 삼키고 "error" 청크로 변환해 보내므로,
                # 여기서도 아래 except 블록과 동일하게 선차감분을 환불해야 한다.
                await _refund_prededuction(db, user_id, is_test_user)
                yield f"data: {chunk_json}\n\n"

    except Exception:
        # AI 스트리밍 실패 → 선차감 전액 환불
        await _refund_prededuction(db, user_id, is_test_user)
        raise


async def _refund_prededuction(db: AsyncSession, user_id: UUID, is_test_user: bool) -> None:
    """AI 응답 실패 시 선차감된 토큰(최대 비용)을 전액 환불한다."""
    if is_test_user:
        return
    try:
        await credit(
            db, user_id, DRAFT_TOKEN_COST,
            TokenTransactionType.CHAT_REFUND, "AI 오류 전액 환불"
        )
        await db.commit()
    except Exception:
        logger.exception("환불 실패: user_id=%s amount=%d", user_id, DRAFT_TOKEN_COST)


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
    remaining_chats: int | None = None,
    remaining_drafts: int | None = None,
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
        remaining_drafts=remaining_drafts,
    )
