from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QuestionCreate(BaseModel):
    """문항 단건 생성 요청"""

    question: str  # 문항 내용
    max_length: int | None = None  # 글자수 제한
    order: int  # 순서


class QuestionBulkCreate(BaseModel):
    """문항 일괄 생성 요청"""

    questions: list[QuestionCreate]


class QuestionUpdate(BaseModel):
    """문항 수정 요청"""

    question: str | None = None
    max_length: int | None = None
    answer: str | None = None


class QuestionRead(BaseModel):
    """문항 조회 응답"""

    id: UUID
    project_id: UUID
    user_id: UUID
    question: str
    max_length: int | None
    order: int
    answer: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionListItem(BaseModel):
    """문항 목록 조회 응답 (간략)"""

    id: UUID
    question: str
    max_length: int | None
    order: int
    answer: str | None

    model_config = ConfigDict(from_attributes=True)


class QuestionReorder(BaseModel):
    """문항 순서 변경 요청"""

    question_ids: list[UUID]  # 새로운 순서대로 정렬된 ID 목록
