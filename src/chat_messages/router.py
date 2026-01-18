from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import MessageRequest, MessageResponse
from .service import (
    create_user_message,
    create_assistant_message,
    get_chat_by_id
)
from src.database import get_async_db

router = APIRouter()


@router.post("/message", response_model=MessageResponse)
async def send_message(
    data: MessageRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """메시지 전송 API
    
    Args:
        data: MessageRequest (chat_id, experience_ids, content)
        db: Database AsyncSession
    
    Returns:
        MessageResponse (chat_message_id, is_draft)
    
    Raises:
        404: Chat not found
    """
    
    # 1. Chat 조회
    chat = await get_chat_by_id(db, data.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # 2. 사용자 메시지 생성
    user_msg = await create_user_message(
        db=db,
        chat_id=data.chat_id,
        content=data.content,
        experience_ids=data.experience_ids
    )
    
    # 3. AI 응답 생성 (임시)
    ai_response = "테스트 응답입니다. RAG는 이후 구현"
    
    # 4. AI 메시지 생성
    ai_msg = await create_assistant_message(
        db=db,
        chat_id=data.chat_id,
        content=ai_response,
        experience_ids=data.experience_ids,
        user_content=data.content
    )
    
    return MessageResponse(
        chat_message_id=ai_msg.id,
        is_draft=ai_msg.is_draft
    )