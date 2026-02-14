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


class ExperienceFormatType(str, Enum):
    """Format types for experiences."""

    STAR = "STAR"  # Situation, Task, Action, Result
    PSI = "PSI"  # Problem, Solution, Insight
    FREE = "FREE"  # Free format


class ExperienceBase(BaseModel):
    """Base model for Experience with multiple format types."""

    title: str = Field(..., min_length=1, max_length=200, description="경험 제목")
    start_date: dt.date = Field(..., description="경험 시작 날짜 (YYYY-MM-DD)")
    end_date: dt.date | None = Field(None, description="경험 종료 날짜 (YYYY-MM-DD)")
    experience_type: ExperienceType = Field(..., description="경험 타입")
    format_type: ExperienceFormatType = Field(default=ExperienceFormatType.STAR, description="경험 형식 (STAR/PSI/FREE)")
    category: ExperienceCategory = Field(..., description="카테고리")
    tags: str = Field(..., description="AI 자동 생성 태그 (쉼표로 구분, 1~3개)")

    # STAR format fields (optional, used when format_type=STAR)
    situation: str | None = Field(None, min_length=1, description="상황 (STAR의 S)")
    task: str | None = Field(None, min_length=1, description="과제 (STAR의 T)")
    action: str | None = Field(None, min_length=1, description="행동 (STAR의 A)")
    result: str | None = Field(None, min_length=1, description="결과 (STAR의 R)")

    # PSI format fields (optional, used when format_type=PSI)
    problem: str | None = Field(None, min_length=1, description="문제 (PSI의 P)")
    solution: str | None = Field(None, min_length=1, description="해결책 (PSI의 S)")
    insight: str | None = Field(None, min_length=1, description="인사이트 (PSI의 I)")

    # Free format field (optional, used when format_type=FREE)
    content: str | None = Field(None, min_length=1, description="자유 형식 내용")


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
            "examples": [
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
            ]
        }
