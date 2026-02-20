"""Experience API request/response schemas."""

import datetime as dt
from datetime import datetime

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.experience.models import ExperienceCategory, ExperienceFormatType, ExperienceType


class ExperienceCreate(BaseModel):
    """Schema for creating a new experience. Supports all format types (STAR/PSI/FREE)."""

    title: str = Field(..., min_length=1, max_length=200, description="경험 제목")
    start_date: dt.date = Field(..., description="경험 시작 날짜")
    end_date: dt.date | None = Field(None, description="경험 종료 날짜")
    experience_type: ExperienceType = Field(..., description="경험 타입")
    format_type: ExperienceFormatType = Field(..., description="경험 형식 (STAR/PSI/FREE)")

    # STAR format fields (required when format_type=STAR)
    situation: str | None = Field(None, min_length=1, max_length=5000, description="상황 (STAR의 S)")
    task: str | None = Field(None, min_length=1, max_length=5000, description="과제 (STAR의 T)")
    action: str | None = Field(None, min_length=1, max_length=5000, description="행동 (STAR의 A)")
    result: str | None = Field(None, min_length=1, max_length=5000, description="결과 (STAR의 R)")

    # PSI format fields (required when format_type=PSI)
    problem: str | None = Field(None, min_length=1, max_length=5000, description="문제 (PSI의 P)")
    solution: str | None = Field(None, min_length=1, max_length=5000, description="해결책 (PSI의 S)")
    insight: str | None = Field(None, min_length=1, max_length=5000, description="인사이트 (PSI의 I)")

    # Free format field (required when format_type=FREE)
    content: str | None = Field(None, min_length=1, max_length=10000, description="자유 형식 내용")

    @field_validator("end_date", mode="before")
    @classmethod
    def validate_end_date(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            if v.strip() == "":
                return None
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", v.strip()):
                raise ValueError("날짜 형식은 YYYY-MM-DD이어야 합니다.")
            return v.strip()
        return v
      
    @model_validator(mode="after")
    def validate_format_fields(self):
        # Validate date range
        if self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")

        # Validate format-specific fields
        if self.format_type == ExperienceFormatType.STAR:
            if not all([self.situation, self.task, self.action, self.result]):
                raise ValueError("STAR format requires: situation, task, action, result")
        elif self.format_type == ExperienceFormatType.PSI:
            if not all([self.problem, self.solution, self.insight]):
                raise ValueError("PSI format requires: problem, solution, insight")
        elif self.format_type == ExperienceFormatType.FREE:
            if not self.content:
                raise ValueError("FREE format requires: content")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example":
                {
                    "id": "7b74a7a4-365c-4351-b3a9-ffd5a7da2bce",
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "title": "AI 챗봇 서비스 개발",
                    "start_date": "2024-06-01",
                    "end_date": "2024-06-15",
                    "experience_type": "동아리 활동",
                    "format_type": "STAR",
                    "tags": "AI/LLM, API연동, 백엔드",
                    "created_at": "2026-02-06T06:16:41.312815",
                    "updated_at": "2026-02-06T06:16:41.312816",
                    "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                    "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                    "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
                    "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
                    "problem": None,
                    "solution": None,
                    "insight": None,
                    "content": None
                }

        }
    )


class ExperienceUpdate(BaseModel):
    """Schema for updating an existing experience (partial update). Supports all format types."""

    # Common fields
    title: str | None = Field(None, min_length=1, max_length=200, description="경험 제목")
    start_date: dt.date | None = Field(None, description="경험 시작 날짜")
    end_date: dt.date | None = Field(None, description="경험 종료 날짜")
    experience_type: ExperienceType | None = Field(None, description="경험 타입")

    # STAR format fields
    situation: str | None = Field(None, min_length=1, max_length=5000, description="상황 (STAR의 S)")
    task: str | None = Field(None, min_length=1, max_length=5000, description="과제 (STAR의 T)")
    action: str | None = Field(None, min_length=1, max_length=5000, description="행동 (STAR의 A)")
    result: str | None = Field(None, min_length=1, max_length=5000, description="결과 (STAR의 R)")

    # PSI format fields
    problem: str | None = Field(None, min_length=1, max_length=5000, description="문제 (PSI의 P)")
    solution: str | None = Field(None, min_length=1, max_length=5000, description="해결책 (PSI의 S)")
    insight: str | None = Field(None, min_length=1, max_length=5000, description="인사이트 (PSI의 I)")

    # Free format field
    content: str | None = Field(None, min_length=1, max_length=10000, description="자유 형식 내용")

    @field_validator("end_date", mode="before")
    @classmethod
    def validate_end_date(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            if v.strip() == "":
                return None
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", v.strip()):
                raise ValueError("날짜 형식은 YYYY-MM-DD이어야 합니다.")
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_date_range(self):
        # Only validate if both dates are provided
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example":
            {
                "title": "AI 챗봇 서비스 개발 및 배포",
                "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰으며, 월 활성 사용자 1000명을 달성했습니다.",
            }
        }
    )


class ExperienceRead(BaseModel):
    """Schema for reading an experience."""

    id: str = Field(..., description="경험 ID")
    user_id: str = Field(..., description="소유자 ID")
    title: str = Field(..., description="경험 제목")
    start_date: dt.date = Field(..., description="경험 시작 날짜")
    end_date: dt.date | None = Field(None, description="경험 종료 날짜")
    experience_type: ExperienceType = Field(..., description="경험 타입")
    format_type: ExperienceFormatType = Field(..., description="경험 형식 (STAR/PSI/FREE)")
    category: ExperienceCategory = Field(..., description="카테고리")
    tags: str = Field(..., description="AI 자동 생성 태그 (쉼표로 구분)")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")

    # STAR format fields (optional)
    situation: str | None = Field(None, description="상황 (STAR의 S)")
    task: str | None = Field(None, description="과제 (STAR의 T)")
    action: str | None = Field(None, description="행동 (STAR의 A)")
    result: str | None = Field(None, description="결과 (STAR의 R)")

    # PSI format fields (optional)
    problem: str | None = Field(None, description="문제 (PSI의 P)")
    solution: str | None = Field(None, description="해결책 (PSI의 S)")
    insight: str | None = Field(None, description="인사이트 (PSI의 I)")

    # Free format field (optional)
    content: str | None = Field(None, description="자유 형식 내용")

    model_config = ConfigDict(
        json_schema_extra={
            "example":
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                "title": "AI 챗봇 서비스 개발",
                "start_date": "2024-06-01",
                "end_date": "2024-06-15",
                "experience_type": "동아리 활동",
                "format_type": "STAR",
                "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
                "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
                "category": "기술적 전문성",
                "tags": "AI/LLM, API연동, 백엔드",
                "created_at": "2024-06-15T10:00:00Z",
                "updated_at": "2024-06-15T10:00:00Z",
                "problem": None,
                "solution": None,
                "insight": None,
                "content": None
            }
        }
    )


class ExperienceListResponse(BaseModel):
    """Schema for paginated list of experiences."""

    experiences: list[ExperienceRead] = Field(..., description="경험 목록")
    total: int = Field(..., description="전체 경험 개수")
    limit: int = Field(..., description="페이지당 항목 수")
    offset: int = Field(..., description="오프셋")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "experiences": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                        "title": "AI 챗봇 서비스 개발",
                        "start_date": "2024-06-01",
                        "end_date": "2024-06-15",
                        "experience_type": "동아리 활동",
                        "format_type": "STAR",
                        "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                        "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                        "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                        "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                        "category": "기술적 전문성",
                        "tags": "AI/LLM, API연동, 백엔드",
                        "created_at": "2024-06-15T10:00:00Z",
                        "updated_at": "2024-06-15T10:00:00Z",
                        "problem": None,
                        "solution": None,
                        "insight": None,
                        "content": None
                    },
                    {
                        "id": "234e5678-e89b-12d3-a456-426614174111",
                        "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                        "title": "팀 협업 프로세스 개선",
                        "start_date": "2024-03-01",
                        "end_date": "2024-05-30",
                        "experience_type": "정규직",
                        "format_type": "PSI",
                        "problem": "팀원 간 커뮤니케이션이 원활하지 않아 프로젝트 진행이 지연되었습니다.",
                        "solution": "주간 스탠드업 미팅을 도입하고 Notion으로 작업 현황을 실시간 공유했습니다.",
                        "insight": "정기적인 소통과 투명한 정보 공유가 팀 생산성을 크게 향상시킨다는 것을 배웠습니다.",
                        "category": "협력적 소통",
                        "tags": "커뮤니케이션, 프로세스개선, 협업도구(Notion/Jira/Slack)",
                        "created_at": "2024-05-30T10:00:00Z",
                        "updated_at": "2024-05-30T10:00:00Z",
                        "situation": None,
                        "task": None,
                        "action": None,
                        "result": None,
                        "content": None
                    },
                    {
                        "id": "345e6789-e89b-12d3-a456-426614174222",
                        "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                        "title": "오픈소스 프로젝트 기여",
                        "start_date": "2024-01-10",
                        "end_date": "2024-02-20",
                        "experience_type": "개인 활동",
                        "format_type": "FREE",
                        "content": "React 라이브러리의 버그를 발견하고 수정하는 PR을 제출했습니다. 커뮤니티의 피드백을 받아 코드를 개선했고, 최종적으로 메인 브랜치에 머지되었습니다. 이 과정에서 코드 리뷰 문화와 오픈소스 기여 프로세스를 깊이 이해하게 되었습니다.",
                        "category": "기술적 전문성",
                        "tags": "프론트엔드, 코드리뷰, 문제해결",
                        "created_at": "2024-02-20T10:00:00Z",
                        "updated_at": "2024-02-20T10:00:00Z",
                        "situation": None,
                        "task": None,
                        "action": None,
                        "result": None,
                        "problem": None,
                        "solution": None,
                        "insight": None
                    }
                ],
                "total": 3,
                "limit": 100,
                "offset": 0,
            }
        }
    )


class ExperienceSearchResponse(BaseModel):
    """Schema for a single search result with score."""

    experience: ExperienceRead = Field(..., description="경험 데이터")
    score: float = Field(..., description="유사도 점수 (0~1, 높을수록 관련성 높음)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "experience": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                    "title": "AI 챗봇 서비스 개발",
                    "start_date": "2024-06-01",
                    "end_date": "2024-06-15",
                    "experience_type": "동아리 활동",
                    "format_type": "STAR",
                    "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                    "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                    "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                    "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                    "category": "기술적 전문성",
                    "tags": "AI/LLM, API연동, 백엔드",
                    "created_at": "2024-06-15T10:00:00Z",
                    "updated_at": "2024-06-15T10:00:00Z",
                    "problem": None,
                    "solution": None,
                    "insight": None,
                    "content": None
                },
                "score": 0.92,
            }
        }
    )


class ExperienceSearchResult(BaseModel):
    """Schema for search results container."""

    results: list[ExperienceSearchResponse] = Field(..., description="검색 결과 목록")
    query: str = Field(..., description="검색 쿼리")
    total: int = Field(..., description="검색 결과 개수")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "experience": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                            "title": "AI 챗봇 서비스 개발",
                            "start_date": "2024-06-01",
                            "end_date": "2024-06-15",
                            "experience_type": "동아리 활동",
                            "format_type": "STAR",
                            "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                            "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                            "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                            "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                            "category": "기술적 전문성",
                            "tags": "AI/LLM, API연동, 백엔드",
                            "created_at": "2024-06-15T10:00:00Z",
                            "updated_at": "2024-06-15T10:00:00Z",
                            "problem": None,
                            "solution": None,
                            "insight": None,
                            "content": None
                        },
                        "score": 0.92,
                    },
                    {
                        "experience": {
                            "id": "234e5678-e89b-12d3-a456-426614174111",
                            "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                            "title": "팀 협업 프로세스 개선",
                            "start_date": "2024-03-01",
                            "end_date": "2024-05-30",
                            "experience_type": "정규직",
                            "format_type": "PSI",
                            "problem": "팀원 간 커뮤니케이션이 원활하지 않아 프로젝트 진행이 지연되었습니다.",
                            "solution": "주간 스탠드업 미팅을 도입하고 Notion으로 작업 현황을 실시간 공유했습니다.",
                            "insight": "정기적인 소통과 투명한 정보 공유가 팀 생산성을 크게 향상시킨다는 것을 배웠습니다.",
                            "category": "협력적 소통",
                            "tags": "커뮤니케이션, 프로세스개선, 협업도구(Notion/Jira/Slack)",
                            "created_at": "2024-05-30T10:00:00Z",
                            "updated_at": "2024-05-30T10:00:00Z",
                            "situation": None,
                            "task": None,
                            "action": None,
                            "result": None,
                            "content": None
                        },
                        "score": 0.87,
                    },
                    {
                        "experience": {
                            "id": "345e6789-e89b-12d3-a456-426614174222",
                            "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                            "title": "오픈소스 프로젝트 기여",
                            "start_date": "2024-01-10",
                            "end_date": "2024-02-20",
                            "experience_type": "개인 활동",
                            "format_type": "FREE",
                            "content": "React 라이브러리의 버그를 발견하고 수정하는 PR을 제출했습니다. 커뮤니티의 피드백을 받아 코드를 개선했고, 최종적으로 메인 브랜치에 머지되었습니다. 이 과정에서 코드 리뷰 문화와 오픈소스 기여 프로세스를 깊이 이해하게 되었습니다.",
                            "category": "기술적 전문성",
                            "tags": "프론트엔드, 코드리뷰, 문제해결",
                            "created_at": "2024-02-20T10:00:00Z",
                            "updated_at": "2024-02-20T10:00:00Z",
                            "situation": None,
                            "task": None,
                            "action": None,
                            "result": None,
                            "problem": None,
                            "solution": None,
                            "insight": None
                        },
                        "score": 0.81,
                    }
                ],
                "query": "프로젝트 경험",
                "total": 3,
            }
        }
    )


class ExperienceWithQuestionSimilarity(BaseModel):
    """Schema for experience with question similarity score."""

    experience: ExperienceRead = Field(..., description="경험 데이터")
    similarity_score: float = Field(..., description="질문과의 유사도 점수 (0~1, 높을수록 관련성 높음)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "experience": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                    "title": "AI 챗봇 서비스 개발",
                    "start_date": "2024-06-01",
                    "end_date": "2024-06-15",
                    "experience_type": "동아리 활동",
                    "format_type": "STAR",
                    "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                    "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                    "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                    "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                    "category": "기술적 전문성",
                    "tags": "AI/LLM, API연동, 백엔드",
                    "created_at": "2024-06-15T10:00:00Z",
                    "updated_at": "2024-06-15T10:00:00Z",
                    "problem": None,
                    "solution": None,
                    "insight": None,
                    "content": None
                },
                "similarity_score": 0.87,
            }
        }
    )


class ExperienceQuestionMatchResult(BaseModel):
    """Schema for experiences matched with question."""

    experiences: list[ExperienceWithQuestionSimilarity] = Field(..., description="유사도가 높은 순서로 정렬된 경험 목록")
    total: int = Field(..., description="전체 경험 개수")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "experiences": [
                    {
                        "experience": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                            "title": "AI 챗봇 서비스 개발",
                            "start_date": "2024-06-01",
                            "end_date": "2024-06-15",
                            "experience_type": "동아리 활동",
                            "format_type": "STAR",
                            "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                            "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                            "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                            "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                            "category": "기술적 전문성",
                            "tags": "AI/LLM, API연동, 백엔드",
                            "created_at": "2024-06-15T10:00:00Z",
                            "updated_at": "2024-06-15T10:00:00Z",
                            "problem": None,
                            "solution": None,
                            "insight": None,
                            "content": None
                        },
                        "similarity_score": 0.87,
                    },
                    {
                        "experience": {
                            "id": "234e5678-e89b-12d3-a456-426614174111",
                            "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                            "title": "팀 협업 프로세스 개선",
                            "start_date": "2024-03-01",
                            "end_date": "2024-05-30",
                            "experience_type": "정규직",
                            "format_type": "PSI",
                            "problem": "팀원 간 커뮤니케이션이 원활하지 않아 프로젝트 진행이 지연되었습니다.",
                            "solution": "주간 스탠드업 미팅을 도입하고 Notion으로 작업 현황을 실시간 공유했습니다.",
                            "insight": "정기적인 소통과 투명한 정보 공유가 팀 생산성을 크게 향상시킨다는 것을 배웠습니다.",
                            "category": "협력적 소통",
                            "tags": "커뮤니케이션, 프로세스개선, 협업도구(Notion/Jira/Slack)",
                            "created_at": "2024-05-30T10:00:00Z",
                            "updated_at": "2024-05-30T10:00:00Z",
                            "situation": None,
                            "task": None,
                            "action": None,
                            "result": None,
                            "content": None
                        },
                        "similarity_score": 0.82,
                    },
                    {
                        "experience": {
                            "id": "345e6789-e89b-12d3-a456-426614174222",
                            "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                            "title": "오픈소스 프로젝트 기여",
                            "start_date": "2024-01-10",
                            "end_date": "2024-02-20",
                            "experience_type": "개인 활동",
                            "format_type": "FREE",
                            "content": "React 라이브러리의 버그를 발견하고 수정하는 PR을 제출했습니다. 커뮤니티의 피드백을 받아 코드를 개선했고, 최종적으로 메인 브랜치에 머지되었습니다. 이 과정에서 코드 리뷰 문화와 오픈소스 기여 프로세스를 깊이 이해하게 되었습니다.",
                            "category": "기술적 전문성",
                            "tags": "프론트엔드, 코드리뷰, 문제해결",
                            "created_at": "2024-02-20T10:00:00Z",
                            "updated_at": "2024-02-20T10:00:00Z",
                            "situation": None,
                            "task": None,
                            "action": None,
                            "result": None,
                            "problem": None,
                            "solution": None,
                            "insight": None
                        },
                        "similarity_score": 0.75,
                    }
                ],
                "total": 3,
            }
        }
    )
