from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import ChatRequest, ChatResponse
from .service import send_chat_flow
from src.database import get_async_db
from .swagger import SEND_CHAT_SWAGGER

router = APIRouter()


@router.post(
    "/projects/chats",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    **SEND_CHAT_SWAGGER,
)
async def send_chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """메시지 전송 API"""

    ai_msg = await send_chat_flow(
        db=db,
        question_id=data.question_id,
        content=data.content,
        experience_ids=data.experience_ids,
    )

    return ChatResponse(
        chat_id=ai_msg.id,
        is_draft=ai_msg.is_draft
    )
