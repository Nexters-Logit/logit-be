from pydantic import BaseModel, field_validator  # ← 추가!
from uuid import UUID
from typing import List

class MessageRequest(BaseModel):
    """메시지 전송 요청
    
    POST /api/v1/chats/message
    """
    
    chat_id: UUID
    experience_ids: List[int] | None = None
    content: str
    
    @field_validator("experience_ids")
    @classmethod
    def validate_experience_ids(cls, v: List[int] | None) -> List[int] | None:
        """경험 ID 검증 (최대 3개, 중복 불가)"""
        if v is None:
            return None
        
        if len(v) == 0:
            return []
        
        if len(v) > 3:
            raise ValueError("최대 3개의 경험만 선택할 수 있습니다")
        
        if len(v) != len(set(v)):
            raise ValueError("중복된 경험을 선택할 수 없습니다")
        
        return v


class MessageResponse(BaseModel):
    """메시지 전송 응답
    
    POST /api/v1/chats/message
    """
    
    chat_message_id: UUID
    is_draft: bool