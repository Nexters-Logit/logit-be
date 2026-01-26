"""Experience API request/response schemas."""

import datetime as dt
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.experience.models import ExperienceCategory, ExperienceType


class ExperienceCreate(BaseModel):
    """Schema for creating a new experience."""

    title: str = Field(..., min_length=1, max_length=200, description="경험 제목")
    date: dt.date = Field(..., description="경험 발생 날짜")
    experience_type: ExperienceType = Field(..., description="경험 타입")
    situation: str = Field(..., min_length=1, description="상황 (STAR의 S)")
    task: str = Field(..., min_length=1, description="과제 (STAR의 T)")
    action: str = Field(..., min_length=1, description="행동 (STAR의 A)")
    result: str = Field(..., min_length=1, description="결과 (STAR의 R)")
    category: ExperienceCategory = Field(..., description="카테고리")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "AI 챗봇 서비스 개발",
                "date": "2024-06-15",
                "experience_type": "동아리 활동",
                "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
                "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
                "category": "기술적 전문성",
            }
        }
    )


class ExperienceUpdate(BaseModel):
    """Schema for updating an existing experience (partial update)."""

    title: str | None = Field(None, min_length=1, max_length=200, description="경험 제목")
    date: dt.date | None = Field(None, description="경험 발생 날짜")
    experience_type: ExperienceType | None = Field(None, description="경험 타입")
    situation: str | None = Field(None, min_length=1, description="상황 (STAR의 S)")
    task: str | None = Field(None, min_length=1, description="과제 (STAR의 T)")
    action: str | None = Field(None, min_length=1, description="행동 (STAR의 A)")
    result: str | None = Field(None, min_length=1, description="결과 (STAR의 R)")
    category: ExperienceCategory | None = Field(None, description="카테고리")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
    date: dt.date = Field(..., description="경험 발생 날짜")
    experience_type: ExperienceType = Field(..., description="경험 타입")
    situation: str = Field(..., description="상황 (STAR의 S)")
    task: str = Field(..., description="과제 (STAR의 T)")
    action: str = Field(..., description="행동 (STAR의 A)")
    result: str = Field(..., description="결과 (STAR의 R)")
    category: ExperienceCategory = Field(..., description="카테고리")
    tags: str = Field(..., description="AI 자동 생성 태그 (쉼표로 구분)")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                "title": "AI 챗봇 서비스 개발",
                "date": "2024-06-15",
                "experience_type": "동아리 활동",
                "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
                "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
                "category": "기술적 전문성",
                "tags": "전문성, 문제해결력, 고객 이해력",
                "created_at": "2024-06-15T10:00:00Z",
                "updated_at": "2024-06-15T10:00:00Z",
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
                        "date": "2024-06-15",
                        "experience_type": "동아리 활동",
                        "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                        "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                        "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                        "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                        "category": "기술적 전문성",
                        "tags": "전문성, 문제해결력, 고객 이해력",
                        "created_at": "2024-06-15T10:00:00Z",
                        "updated_at": "2024-06-15T10:00:00Z",
                    }
                ],
                "total": 1,
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
                    "date": "2024-06-15",
                    "experience_type": "동아리 활동",
                    "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                    "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                    "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                    "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                    "category": "기술적 전문성",
                    "tags": "전문성, 문제해결력, 고객 이해력",
                    "created_at": "2024-06-15T10:00:00Z",
                    "updated_at": "2024-06-15T10:00:00Z",
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
                            "date": "2024-06-15",
                            "experience_type": "동아리 활동",
                            "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                            "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                            "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발했습니다.",
                            "result": "응답 시간을 70% 단축하고 만족도를 85%로 향상시켰습니다.",
                            "category": "기술적 전문성",
                            "tags": "전문성, 문제해결력, 고객 이해력",
                            "created_at": "2024-06-15T10:00:00Z",
                            "updated_at": "2024-06-15T10:00:00Z",
                        },
                        "score": 0.92,
                    }
                ],
                "query": "AI 챗봇",
                "total": 1,
            }
        }
    )
