from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID
from typing import List
from datetime import datetime

class ChatRequest(BaseModel):
    """메시지 전송 요청"""
    
    question_id: UUID = Field(
        ...,
        description="프로젝트의 문항 ID",
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
                        "question_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "experience_ids": [
                            "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                            "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed"
                        ],
                        "content": "협업 경험을 중심으로 자기소개서를 작성해줘"
                    }
                ]
            }
        }


class ChatHistoryItem(BaseModel):
    """개별 채팅 메시지"""

    id: UUID
    role: str  # "user" or "assistant"
    content: str
    is_draft: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    """채팅 히스토리 조회 응답 (Cursor 기반 페이지네이션)"""

    project_name: str
    project_created_at: datetime
    question_id: UUID
    question: str
    chats: List[ChatHistoryItem]
    experience_ids: List[str] = []
    next_cursor: str | None = Field(
        default=None,
        description="다음 페이지 조회용 cursor (없으면 마지막 페이지)"
    )
    has_more: bool = Field(
        default=False,
        description="더 많은 데이터가 있는지 여부"
    )
    remaining_chats: int = Field(
        description="오늘 남은 채팅 횟수"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_name": "네이버_백엔드개발자",
                    "project_created_at": "2026-01-20T10:00:00Z",
                    "question_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "question": "지원동기 및 향후 목표",
                    "chats": [
                        {
                            "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                            "role": "user",
                            "content": "협업 경험 써줘",
                            "is_draft": False,
                            "created_at": "2026-01-20T10:00:00Z"
                        },
                        {
                            "id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
                            "role": "assistant",
                            "content": "Cardify 프로젝트에서...",
                            "is_draft": True,
                            "created_at": "2026-01-20T10:00:05Z"
                        }
                    ],
                    "experience_ids": [
                        "7c9e6679-7425-40de-944b-e07fc1f90ae7"
                    ],
                    "next_cursor": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
                    "has_more": True,
                    "remaining_chats": 8
                }
            ]
        }
    }


class UpdateAnswerResponse(BaseModel):
    """자기소개서 답변 업데이트 응답"""

    question_id: UUID
    answer: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "answer": "Cardify 프로젝트에서..."
                }
            ]
        }
    } 