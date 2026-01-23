from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .schemas import ChatRequest, ChatHistoryResponse, UpdateAnswerResponse
from .service import send_chat_stream, get_chat_history_response, update_question_answer
from .swagger import SEND_CHAT_SWAGGER, GET_CHAT_HISTORY_SWAGGER, UPDATE_ANSWER_SWAGGER
from src.users.dependencies import ActiveUser, SessionDep
from src.experience.dependencies import QdrantDep

router = APIRouter()


@router.post(
    "/projects/chats",
    response_class=StreamingResponse,
    **SEND_CHAT_SWAGGER,
)
async def send_chat(
    data: ChatRequest,
    session: SessionDep,
    qdrant: QdrantDep,
    current_user: ActiveUser,
):
    """메시지 전송 API (SSE 스트리밍)"""

    return StreamingResponse(
        send_chat_stream(
            db=session,
            qdrant_client=qdrant,
            question_id=data.question_id,
            content=data.content,
            experience_ids=data.experience_ids,
            user_id=current_user.id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get(
    "/projects/chats/{question_id}",
    response_model=ChatHistoryResponse,
    **GET_CHAT_HISTORY_SWAGGER,
)
async def get_chat_messages(
    question_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
    cursor: str | None = Query(
        default=None,
        description="다음 페이지 조회용 cursor (이전 응답의 next_cursor 값)"
    ),
    size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="한 페이지에 가져올 메시지 수 (기본값: 20, 최대: 100)"
    ),
):
    """채팅 히스토리 조회 API"""

    response = await get_chat_history_response(
        session, question_id, current_user.id, cursor=cursor, size=size
    )

    if not response:
        raise HTTPException(404, "Question not found")

    return response


@router.patch(
    "/projects/chats/{chat_id}/answer",
    response_model=UpdateAnswerResponse,
    **UPDATE_ANSWER_SWAGGER,
)
async def update_answer(
    chat_id: UUID,
    session: SessionDep,
    current_user: ActiveUser
):
    """자기소개서 답변 업데이트 API"""

    response = await update_question_answer(session, chat_id, current_user.id)

    if not response:
        raise HTTPException(404, "Chat not found")

    return response