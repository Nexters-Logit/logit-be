from sqlmodel import Session, select
from uuid import UUID
from typing import List

from .models import ChatMessage, ChatRole
from src.chats.models import Chat

def create_user_message(
    db: Session,
    chat_id: UUID,
    content: str,
    experience_ids: List[int]
) -> ChatMessage:
    """사용자 메시지 생성"""
    
    user_msg = ChatMessage(
        chat_id=chat_id,
        role=ChatRole.USER,
        content=content,
        experience_ids=experience_ids
    )
    
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    
    return user_msg

def create_assistant_message(
    db: Session,
    chat_id: UUID,
    content: str,
    experience_ids: List[int],
    assistant_content: str  
) -> ChatMessage:

    # 초안 생성 의도 감지
    is_draft = detect_draft_intent(assistant_content) 
    
    ai_msg = ChatMessage(
        chat_id=chat_id,
        role=ChatRole.ASSISTANT,
        content=content,
        experience_ids=experience_ids,
        is_draft=is_draft 
    )
    
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    
    return ai_msg


def get_chat_by_id(db: Session, chat_id: UUID) -> Chat | None:
    """Chat 조회"""
    
    statement = select(Chat).where(Chat.id == chat_id)
    return db.exec(statement).first()

# todo: 이후 고도화
def detect_draft_intent(content: str) -> bool:
    """초안 생성 의도 감지"""
    
    keywords = ["써줘", "생성", "초안", "작성해줘", "만들어줘"]
    content_lower = content.lower()
    
    return any(keyword in content_lower for keyword in keywords)