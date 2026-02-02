"""Experience domain models for Qdrant storage."""

import datetime as dt
from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ExperienceType(str, Enum):
    """Types of experiences."""

    PART_TIME = "아르바이트"
    INTERN = "인턴"
    FULL_TIME = "정규직"
    FREELANCE = "계약직"
    VOLUNTEER = "봉사 활동"
    PRIZE = "수상경력"
    GROUP_ACTIVITY = "동아리 활동"
    RESEARCH = "연구 활동"
    MILITARY = "군복무"
    OTHER = "개인 활동"


class ExperienceCategory(str, Enum):
    """Categories for classifying experiences."""

    CUSTOMER_VALUE_ORIENTED = "고객 가치 지향"
    TECHNICAL_PROFICIENCY = "기술적 전문성"
    COLLABORATIVE_COMMUNICATION = "협력적 소통"
    LEADERSHIP_INITIATIVE = "주도적 실행력"
    LOGICAL_ANALYTICS = "논리적 분석력"
    CREATIVE_PROBLEM_SOLVING = "창의적 문제해결"
    FLEXIBILITY = "유연한 적응력"
    RESPONSIBILITY = "끈기있는 책임감"


class ExperienceBase(BaseModel):
    """Base model for Experience with STAR format fields."""

    title: str = Field(..., min_length=1, max_length=200, description="경험 제목")
    start_date: dt.date = Field(..., description="경험 시작 날짜 (YYYY-MM-DD)")
    end_date: dt.date = Field(..., description="경험 종료 날짜 (YYYY-MM-DD)")
    experience_type: ExperienceType = Field(..., description="경험 타입")
    situation: str = Field(..., min_length=1, description="상황 (STAR의 S)")
    task: str = Field(..., min_length=1, description="과제 (STAR의 T)")
    action: str = Field(..., min_length=1, description="행동 (STAR의 A)")
    result: str = Field(..., min_length=1, description="결과 (STAR의 R)")
    category: ExperienceCategory = Field(..., description="카테고리")
    tags: str = Field(..., description="AI 자동 생성 태그 (쉼표로 구분, 1~3개)")


class Experience(ExperienceBase):
    """
    Complete Experience model with all fields.
    Stored in Qdrant as payload with vector embedding.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="경험 ID (UUID)")
    user_id: str = Field(..., description="소유자 ID (UUID)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="생성 시간 (UTC)")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="수정 시간 (UTC)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "987fcdeb-51a2-43d7-9876-543210fedcba",
                "title": "AI 챗봇 서비스 개발",
                "start_date": "2024-06-01",
                "end_date": "2024-06-15",
                "experience_type": "동아리 활동",
                "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
                "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
                "category": "기술적 전문성",
                "tags": "AI/LLM, API연동, 백엔드",
                "created_at": "2024-06-15T10:00:00Z",
                "updated_at": "2024-06-15T10:00:00Z",
            }
        }
