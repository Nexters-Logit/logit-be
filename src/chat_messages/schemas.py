from pydantic import BaseModel, Field, field_validator  # ← 추가!
from uuid import UUID
from typing import List

class MessageRequest(BaseModel):
    """메시지 전송 요청
    
    POST /api/v1/chats/message
    """
    
    chat_id: UUID = Field(
        ...,
        description="채팅방 ID",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
    )
    experience_ids: List[str] | None = Field(
        default=None,
        description="선택한 경험 UUID 목록 (선택사항, 최대 3개)",
        examples=[
            [
                "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "7c9e6679-7425-40de-944b-e07fc1f90ae7"
            ],
            None
        ]
    )
    content: str = Field(
        ...,
        description="사용자 메시지 내용",
        min_length=1,
        max_length=5000,
        examples=["협업 경험을 중심으로 자기소개서를 작성해줘"]
    )

    @field_validator("experience_ids")
    @classmethod
    def validate_experience_ids(cls, v: List[str]) -> List[str]:
        """경험 ID 검증"""
        
        if v is None:
            return None
        
        if len(v) == 0:
            return []
        
        if len(v) > 3:
            raise ValueError("최대 3개의 경험만 선택할 수 있습니다")
        
        if len(v) != len(set(v)):
            raise ValueError("중복된 경험을 선택할 수 없습니다")
        
        return v

    model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "chat_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "experience_ids": [
                            "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                            "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed"
                        ],
                        "content": "협업 경험을 중심으로 자기소개서를 작성해줘"
                    }
                ]
            }
        }
    

class MessageResponse(BaseModel):
    """메시지 전송 응답
    
    POST /api/v1/chats/message
    """
    
    chat_message_id: UUID
    is_draft: bool

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "chat_message_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                    "is_draft": True
                }
            ]
        }
    }