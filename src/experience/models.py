"""Experience domain models for Qdrant storage."""

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ExperienceType(str, Enum):
    """Types of experiences."""

    PART_TIME = "part_time"
    INTERN = "intern"
    FULL_TIME = "full_time"
    FREELANCE = "freelance"
    PROJECT = "project"
    VOLUNTEER = "volunteer"
    EDUCATION = "education"
    CONTEST = "contest"
    GROUP_ACTIVITY = "group_activity"
    RESEARCH = "research"
    MILITARY = "military"
    OTHER = "other"


class ExperienceCategory(str, Enum):
    """Categories for classifying experiences."""

    CUSTOMER_VALUE_ORIENTED = "customer_value_oriented"
    TECHNICAL_PROFICIENCY = "technical_proficiency"
    COLLABORATIVE_COMMUNICATION = "collaborative_communication"
    LEADERSHIP_INITIATIVE = "leadership_initiative"
    LOGICAL_ANALYTICS = "logical_analytics"
    CREATIVE_PROBLEM_SOLVING = "creative_problem_solving"
    FLEXIBILITY = "flexibility"
    RESPONSIBILITY = "responsibility"


class ExperienceBase(BaseModel):
    """Base model for Experience with STAR format fields."""

    title: str = Field(..., min_length=1, max_length=200, description="경험 제목")
    date: date = Field(..., description="경험 발생 날짜 (YYYY-MM-DD)")
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
                "date": "2024-06-15",
                "experience_type": "project",
                "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
                "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
                "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
                "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
                "category": "technical_proficiency",
                "tags": "전문성, 문제해결력, 고객 이해력",
                "created_at": "2024-06-15T10:00:00Z",
                "updated_at": "2024-06-15T10:00:00Z",
            }
        }
