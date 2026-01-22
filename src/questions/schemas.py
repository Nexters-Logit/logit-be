"""Question schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionCreate(BaseModel):
    """문항 단건 생성 요청"""

    question: str = Field(..., description="문항 내용")
    max_length: int | None = Field(None, description="글자수 제한")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                "max_length": 1000,
            }
        }
    )


class QuestionUpdate(BaseModel):
    """문항 수정 요청"""

    question: str | None = Field(None, description="문항 내용")
    max_length: int | None = Field(None, description="글자수 제한")
    answer: str | None = Field(None, description="답변 내용")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "지원 동기와 입사 후 포부를 작성해 주세요.",
                "max_length": 800,
                "answer": "저는 카카오에서 사용자 경험을 개선하고 싶습니다...",
            }
        }
    )


class QuestionRead(BaseModel):
    """문항 조회 응답"""

    id: UUID = Field(..., description="문항 ID")
    project_id: UUID = Field(..., description="프로젝트 ID")
    user_id: UUID = Field(..., description="사용자 ID")
    question: str = Field(..., description="문항 내용")
    max_length: int | None = Field(None, description="글자수 제한")
    answer: str | None = Field(None, description="답변 내용")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "project_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                "user_id": "456fcdeb-51a2-43d7-9876-543210fedcba",
                "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                "max_length": 1000,
                "answer": "AI 챗봇 서비스를 개발하며 팀을 이끌었습니다...",
                "created_at": "2024-06-15T10:00:00Z",
                "updated_at": "2024-06-15T10:00:00Z",
            }
        },
    )


class QuestionListItem(BaseModel):
    """문항 목록 조회 응답 (간략)"""

    id: UUID = Field(..., description="문항 ID")
    question: str = Field(..., description="문항 내용")
    max_length: int | None = Field(None, description="글자수 제한")
    answer: str | None = Field(None, description="답변 내용")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                "max_length": 1000,
                "answer": "AI 챗봇 서비스를 개발하며 팀을 이끌었습니다...",
            }
        },
    )


class QuestionListResponse(BaseModel):
    """문항 목록 조회 응답"""

    questions: list[QuestionListItem] = Field(..., description="문항 목록")
    total: int = Field(..., description="전체 문항 수")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "questions": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                        "max_length": 1000,
                        "answer": None,
                    },
                    {
                        "id": "223e4567-e89b-12d3-a456-426614174001",
                        "question": "지원 동기와 입사 후 포부를 작성해 주세요.",
                        "max_length": 800,
                        "answer": "저는 카카오에서 사용자 경험을 개선하고 싶습니다...",
                    },
                ],
                "total": 2,
            }
        }
    )
