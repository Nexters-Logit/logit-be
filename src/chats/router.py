from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from src.config import settings
from src.experience.dependencies import QdrantDep
from src.subscription.models import SubscriptionType
from src.subscription.service import get_active_subscription
from src.tokens.constants import DRAFT_TOKEN_COST
from src.tokens.service import ensure_monthly_tokens
from src.users.dependencies import ActiveUser, SessionDep

from .schemas import ChatHistoryResponse, ChatRequest
from .service import get_chat_history_response, send_chat_stream
from .swagger import GET_CHAT_HISTORY_SWAGGER, SEND_CHAT_SWAGGER

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

    is_test_user = (
        settings.ENVIRONMENT == "dev"
        and str(current_user.id) in settings.TEST_USER_IDS
    )

    if not is_test_user:
        subscription = await get_active_subscription(
            session, current_user.id, SubscriptionType.LOGIT
        )
        _, _, token = await ensure_monthly_tokens(session, current_user.id, subscription)
        await session.commit()

        balance = token.balance
        if balance < DRAFT_TOKEN_COST:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"message": "토큰이 부족합니다.", "balance": balance, "required": DRAFT_TOKEN_COST},
            )

    return StreamingResponse(
        send_chat_stream(
            db=session,
            qdrant_client=qdrant,
            question_id=data.question_id,
            content=data.content,
            experience_ids=data.experience_ids,
            user_id=current_user.id,
            is_test_user=is_test_user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
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

    subscription = await get_active_subscription(
        session, current_user.id, SubscriptionType.LOGIT
    )
    _, _, token = await ensure_monthly_tokens(session, current_user.id, subscription)
    await session.commit()

    balance = token.balance

    response = await get_chat_history_response(
        session, question_id, current_user.id,
        cursor=cursor,
        size=size,
        remaining_chats=balance // CHAT_TOKEN_COST if balance is not None else None,
        remaining_drafts=None,
    )

    if not response:
        raise HTTPException(404, "Question not found")

    return response
