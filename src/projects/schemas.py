from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.questions.schemas import QuestionCreate, QuestionListItem


class ProjectCreate(BaseModel):
    """프로젝트 생성 요청 (문항 포함)"""

    company: str
    employment_type: str | None = None
    recruit_notice: str | None = None
    due_date: date | None = None
    questions: list[QuestionCreate] = []  # 문항 목록


class ProjectUpdate(BaseModel):
    """프로젝트 수정 요청"""

    company: str | None = None
    employment_type: str | None = None
    recruit_notice: str | None = None
    due_date: date | None = None


class ProjectListItem(BaseModel):
    """프로젝트 목록 조회 응답 (간략)"""

    id: UUID
    company: str  # 기업명
    employment_type: str | None  # 직무명/고용형태
    created_at: datetime  # 생성일
    # chat_id: UUID | None  # TODO: 추후 chat 연동 시 추가

    model_config = ConfigDict(from_attributes=True)


class ProjectRead(BaseModel):
    """프로젝트 상세 조회 응답"""

    id: UUID
    user_id: UUID
    company: str
    employment_type: str | None
    recruit_notice: str | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
