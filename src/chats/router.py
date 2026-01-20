from fastapi import APIRouter, status

from .schemas import ChatRequest, ChatResponse
from .service import send_chat_flow
from .swagger import SEND_CHAT_SWAGGER
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.post(
    "/projects/chats",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    **SEND_CHAT_SWAGGER,
)
async def send_chat(
    data: ChatRequest,
    session: SessionDep,
    current_user: ActiveUser,
):
    """메시지 전송 API"""

    ai_msg = await send_chat_flow(
        db=session,
        question_id=data.question_id,
        content=data.content,
        experience_ids=data.experience_ids,
        user_id=current_user.id,
    )

    return ChatResponse(
        chat_id=ai_msg.id,
        is_draft=ai_msg.is_draft
    )
