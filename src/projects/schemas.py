"""Project schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.questions.schemas import QuestionCreate, QuestionListItem


class ProjectCreate(BaseModel):
    """프로젝트 생성 요청 (문항 포함)"""

    company: str = Field(..., description="기업명")
    job_position: str = Field(..., description="직무")
    recruit_notice: str = Field(..., description="채용 공고 내용")
    company_talent: str | None = Field(None, description="회사에서 원하는 인재상")
    due_date: date | None = Field(None, description="마감일")
    questions: list[QuestionCreate] = Field(default=[], description="문항 목록")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company": "카카오",
                "job_position": "백엔드 개발자",
                "recruit_notice": "2024년 상반기 신입 개발자 공개채용",
                "company_talent": "성장 가능성, 협업 능력, 문제 해결 능력",
                "due_date": "2024-12-31",
                "questions": [
                    {
                        "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                        "max_length": 1000,
                    },
                    {
                        "question": "지원 동기와 입사 후 포부를 작성해 주세요.",
                        "max_length": 800,
                    },
                ],
            }
        }
    )


class ProjectUpdate(BaseModel):
    """프로젝트 수정 요청"""

    company: str | None = Field(None, description="기업명")
    job_position: str | None = Field(None, description="직무")
    recruit_notice: str | None = Field(None, description="채용 공고 내용")
    company_talent: str | None = Field(None, description="회사에서 원하는 인재상")
    due_date: date | None = Field(None, description="마감일")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company": "네이버",
                "job_position": "프론트엔드 개발자",
                "company_talent": "성장 가능성, 협업 능력, 문제 해결 능력",
                "due_date": "2025-01-15",
            }
        }
    )


class ProjectListItem(BaseModel):
    """프로젝트 목록 조회 응답 (간략)"""

    id: UUID = Field(..., description="프로젝트 ID")
    company: str = Field(..., description="기업명")
    job_position: str = Field(..., description="직무")
    due_date: date | None = Field(None, description="마감일")
    updated_at: datetime = Field(..., description="최근 활동일")
    question_id: UUID | None = Field(None, description="첫 번째 문항 ID")
    total_questions: int = Field(0, description="전체 문항 수")
    completed_questions: int = Field(0, description="완료 문항 수")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "company": "카카오",
                "job_position": "백엔드 개발자",
                "due_date": "2024-12-31",
                "updated_at": "2024-06-15T10:00:00Z",
                "question_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_questions": 3,
                "completed_questions": 1,
            }
        },
    )


class ProjectRead(BaseModel):
    """프로젝트 상세 조회 응답"""

    id: UUID = Field(..., description="프로젝트 ID")
    user_id: UUID = Field(..., description="사용자 ID")
    company: str = Field(..., description="기업명")
    job_position: str = Field(..., description="직무")
    recruit_notice: str = Field(..., description="채용 공고 내용")
    due_date: date | None = Field(None, description="마감일")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")
    deleted_at: datetime | None = Field(None, description="삭제 시간")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                "company": "카카오",
                "job_position": "백엔드 개발자",
                "recruit_notice": "2024년 상반기 신입 개발자 공개채용",
                "due_date": "2024-12-31",
                "created_at": "2024-06-15T10:00:00Z",
                "updated_at": "2024-06-15T10:00:00Z",
                "deleted_at": None,
            }
        },
    )


class ProjectCreateResponse(BaseModel):
    """프로젝트 생성 응답 (문항 ID 포함)"""

    project: ProjectRead = Field(..., description="프로젝트 정보")
    questions: list[QuestionListItem] = Field(..., description="생성된 문항 목록")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                    "company": "카카오",
                    "job_position": "백엔드 개발자",
                    "recruit_notice": "2024년 상반기 신입 개발자 공개채용",
                    "due_date": "2024-12-31",
                    "created_at": "2024-06-15T10:00:00Z",
                    "updated_at": "2024-06-15T10:00:00Z",
                    "deleted_at": None,
                },
                "questions": [
                    {
                        "id": "333e4567-e89b-12d3-a456-426614174002",
                        "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                        "max_length": 1000,
                        "answer": None,
                    },
                ],
            }
        }
    )


class ProjectListResponse(BaseModel):
    """프로젝트 목록 조회 응답"""

    projects: list[ProjectListItem] = Field(..., description="프로젝트 목록")
    total: int = Field(..., description="전체 프로젝트 수")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "projects": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "company": "카카오",
                        "job_position": "백엔드 개발자",
                        "due_date": "2024-12-31",
                        "updated_at": "2024-06-15T10:00:00Z",
                        "question_id": "123e4567-e89b-12d3-a456-426614174000",
                        "total_questions": 3,
                        "completed_questions": 1,
                    },
                    {
                        "id": "223e4567-e89b-12d3-a456-426614174001",
                        "company": "네이버",
                        "job_position": "프론트엔드 개발자",
                        "due_date": None,
                        "updated_at": "2024-06-14T09:00:00Z",
                        "question_id": "123e4567-e89b-12d3-a456-426614174000",
                        "total_questions": 2,
                        "completed_questions": 0,
                    },
                ],
                "total": 2,
            }
        }
    )


class ProjectDetailResponse(BaseModel):
    """프로젝트 상세 조회 응답 (문항 포함)"""

    project: ProjectRead = Field(..., description="프로젝트 정보")
    questions: list[QuestionListItem] = Field(..., description="문항 목록")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                    "company": "카카오",
                    "job_position": "백엔드 개발자",
                    "recruit_notice": "2024년 상반기 신입 개발자 공개채용",
                    "due_date": "2024-12-31",
                    "created_at": "2024-06-15T10:00:00Z",
                    "updated_at": "2024-06-15T10:00:00Z",
                    "deleted_at": None,
                },
                "questions": [
                    {
                        "id": "333e4567-e89b-12d3-a456-426614174002",
                        "question": "본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
                        "max_length": 1000,
                        "answer": None,
                    },
                    {
                        "id": "444e4567-e89b-12d3-a456-426614174003",
                        "question": "지원 동기와 입사 후 포부를 작성해 주세요.",
                        "max_length": 800,
                        "answer": "저는 카카오에서 사용자 경험을 개선하고 싶습니다...",
                    },
                ],
            }
        }
    )
