from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from .schemas import MessageRequest, MessageResponse
from .service import (
    create_user_message,
    create_assistant_message,
    get_chat_by_id,
    detect_draft_intent
)
from database import get_db

router = APIRouter(prefix="/api/v1/chats", tags=["chat_messages"])


@router.post("/message", response_model=MessageResponse)
async def send_message(
    data: MessageRequest,
    db: Session = Depends(get_db)
):
    """메시지 전송 API
    
    Args:
        data: MessageRequest (chat_id, experience_ids, content)
        db: Database session
    
    Returns:
        MessageResponse (chat_message_id, is_draft)
    
    Raises:
        404: Chat not found
    """
    
    # 1. Chat 조회
    chat = get_chat_by_id(db, data.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # 2. 사용자 메시지 생성
    user_msg = create_user_message(
        db=db,
        chat_id=data.chat_id,
        content=data.content,
        experience_ids=data.experience_ids
    )
    
    # 3. 초안 의도 감지
    is_draft_request = detect_draft_intent(data.content)
    
    # 4. 경험 없이 초안 요청 시 - 안내 메시지
    if is_draft_request and (not data.experience_ids or len(data.experience_ids) == 0):
        ai_msg = create_assistant_message(
            db=db,
            chat_id=data.chat_id,
            # pm 질문 후 수정 예정 
            content="자기소개서 작성을 도와드릴게요.",
            experience_ids=None,
            user_content=data.content
        )
        
        return MessageResponse(
            chat_message_id=ai_msg.id,
            is_draft=ai_msg.is_draft
        )
    
    # 5. AI 응답 생성 (임시 - RAG는 나중에 구현)
    ai_response = "테스트 응답입니다. RAG는 다음 단계에서 구현합니다."
    
    # 6. AI 메시지 생성
    ai_msg = create_assistant_message(
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