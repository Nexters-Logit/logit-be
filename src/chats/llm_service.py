import json
import logging
from enum import Enum
from typing import AsyncGenerator
from uuid import UUID

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.experience.models import Experience, ExperienceFormatType
from src.experience.service import get_experience
from .prompts import (
    CLASSIFICATION_PROMPT,
    STORYLINE_PROMPT,
    GENERATION_PROMPT,
    FEWSHOT_EXAMPLES,
    REVIEW_PROMPT,
    REVISION_PROMPT,
    LENGTH_ADJUSTMENT_PROMPT,
    CONVERSATION_SYSTEM_PROMPT,
)
from .chat_history import PostgresChatMessageHistory
from .dependencies import LLMProvider, get_llm_provider

logger = logging.getLogger(__name__)


# ============================================================
# Pydantic Schemas
# ============================================================

class QuestionType(str, Enum):
    MOTIVATION = "지원동기"
    COMPETENCY = "직무역량"
    COLLABORATION = "협업소통"
    PROBLEM_SOLVING = "문제해결"
    GROWTH = "성장가치관"
    OTHER = "기타"


class RequestClassification(BaseModel):
    is_cover_letter_request: bool = Field(
        description="자기소개서 작성/재작성 요청이면 True, 단순 질문/피드백/수정 요청이면 False"
    )
    question_type: QuestionType = Field(
        description="문항 유형 분류 (자기소개서 요청일 때만 의미 있음)"
    )


class StorylineExperience(BaseModel):
    title: str = Field(description="경험 제목")
    role: str = Field(description="주 경험 / 보조 경험")
    key_facts: list[str] = Field(description="이 경험에서 사용할 핵심 사실 (1~3개)")
    how_to_mention: str = Field(description="이 경험을 어떻게 언급할지 한 줄 가이드")


class Storyline(BaseModel):
    core_message: str = Field(description="자기소개서의 핵심 메시지 (한 문장)")
    opening: str = Field(description="도입부 방향 (어떤 장면/사실로 시작할지)")
    development: str = Field(description="전개부 방향 (주 경험을 어떻게 풀어갈지)")
    conclusion: str = Field(description="마무리 방향 (어떻게 직무/회사와 연결할지)")
    experiences: list[StorylineExperience] = Field(description="경험별 역할 및 사용 계획")


class ReviewResult(BaseModel):
    has_listing_pattern: bool = Field(
        description="경험을 나열식으로 서술하고 있으면 True"
    )
    has_hallucination: bool = Field(
        description="경험 정보에 없는 사실이 포함되어 있으면 True"
    )
    feedback: str = Field(
        description="구체적인 개선 피드백 (문제가 없으면 빈 문자열)"
    )


# ============================================================
# Experience Formatting Helpers
# ============================================================

def _format_experience_with_role(exp: Experience, is_primary: bool, score: float) -> str:
    """경험을 역할(주/보조) 태그와 함께 프롬프트용 텍스트로 변환"""
    role_tag = "[주 경험 - 상세 서술]" if is_primary else "[보조 경험 - 간략 언급]"

    lines = [
        f"### {exp.title} {role_tag} (적합도: {score:.2f})",
        f"- 유형: {exp.experience_type}",
        f"- 카테고리: {exp.category}",
    ]

    if exp.format_type == ExperienceFormatType.STAR:
        if exp.situation:
            lines.append(f"- 상황(S): {exp.situation}")
        if exp.task:
            lines.append(f"- 과제(T): {exp.task}")
        if exp.action:
            lines.append(f"- 행동(A): {exp.action}")
        if exp.result:
            lines.append(f"- 결과(R): {exp.result}")
    elif exp.format_type == ExperienceFormatType.PSI:
        if exp.problem:
            lines.append(f"- 문제(P): {exp.problem}")
        if exp.solution:
            lines.append(f"- 해결(S): {exp.solution}")
        if exp.insight:
            lines.append(f"- 인사이트(I): {exp.insight}")
    else:  # FREE
        if exp.content:
            lines.append(f"- 내용: {exp.content}")

    return "\n".join(lines)


def _format_experiences_with_roles(experiences: list[Experience]) -> str:
    """
    경험 목록을 역할 분배 포함 텍스트로 변환
    - 첫 번째 경험: 주 경험 (사용자가 가장 적합하다고 선택한 순서 기준)
    - 나머지: 보조 경험
    """
    if not experiences:
        return "선택된 경험이 없습니다."

    mock_scores = [1.0, 0.7, 0.4]
    parts = []
    for i, exp in enumerate(experiences):
        is_primary = (i == 0)
        score = mock_scores[min(i, len(mock_scores) - 1)]
        parts.append(_format_experience_with_role(exp, is_primary, score))

    return "\n\n".join(parts)


def _format_experiences_plain(experiences: list[Experience]) -> str:
    """검수/수정용 단순 경험 텍스트 (역할 태그 없음)"""
    if not experiences:
        return "경험 없음"

    parts = []
    for exp in experiences:
        lines = [f"### {exp.title}"]
        if exp.format_type == ExperienceFormatType.STAR:
            if exp.situation:
                lines.append(f"- 상황: {exp.situation}")
            if exp.task:
                lines.append(f"- 과제: {exp.task}")
            if exp.action:
                lines.append(f"- 행동: {exp.action}")
            if exp.result:
                lines.append(f"- 결과: {exp.result}")
        elif exp.format_type == ExperienceFormatType.PSI:
            if exp.problem:
                lines.append(f"- 문제: {exp.problem}")
            if exp.solution:
                lines.append(f"- 해결: {exp.solution}")
            if exp.insight:
                lines.append(f"- 인사이트: {exp.insight}")
        else:  # FREE
            if exp.content:
                lines.append(f"- 내용: {exp.content}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def get_experiences_by_ids(
    qdrant_client: QdrantClient,
    experience_ids: list[str],
    user_id: str,
) -> list[Experience]:
    """experience_ids로 경험 목록 조회 (선택 순서 유지)"""
    experiences = []
    for exp_id in experience_ids:
        try:
            exp = get_experience(qdrant_client, exp_id, user_id)
            experiences.append(exp)
        except Exception:
            continue
    return experiences


# ============================================================
# Pipeline Step Functions
# ============================================================

async def classify_request(
    user_message: str,
    question: str,
    provider: LLMProvider,
) -> RequestClassification:
    """1단계: 요청 분류 + 문항 유형 분류"""
    structured_llm = provider.classification_llm.with_structured_output(RequestClassification)
    return await structured_llm.ainvoke(
        CLASSIFICATION_PROMPT.format(
            user_message=user_message,
            question=question,
        )
    )


async def design_storyline(
    question: str,
    max_length: int | None,
    company: str,
    experiences: list[Experience],
    provider: LLMProvider,
) -> Storyline:
    """2단계: 적합성 점수 기반 역할 분배 + 스토리라인 설계"""
    experiences_text = _format_experiences_with_roles(experiences)
    structured_llm = provider.classification_llm.with_structured_output(Storyline)
    return await structured_llm.ainvoke(
        STORYLINE_PROMPT.format(
            question=question,
            max_length=max_length or "제한 없음",
            company=company,
            experiences=experiences_text,
        )
    )


async def generate_draft_text(
    storyline: Storyline,
    question_type: QuestionType,
    question: str,
    max_length: int | None,
    company: str,
    recruit_notice: str | None,
    provider: LLMProvider,
) -> str:
    """3단계: 스토리라인 + few-shot 기반 초안 생성 (비스트리밍)"""
    experience_plan = "\n".join(
        f"- [{exp.role}] {exp.title}: {exp.how_to_mention}\n"
        f"  핵심 사실: {', '.join(exp.key_facts)}"
        for exp in storyline.experiences
    )

    fewshot = FEWSHOT_EXAMPLES.get(question_type.value, "")
    if not fewshot:
        fewshot = "참고 예시 없음"

    prompt = GENERATION_PROMPT.format(
        company=company,
        recruit_notice=recruit_notice or "채용공고 정보 없음",
        question=question,
        max_length=max_length or "제한 없음",
        min_length=int(max_length * 0.9) if max_length else 0,
        core_message=storyline.core_message,
        opening=storyline.opening,
        development=storyline.development,
        conclusion=storyline.conclusion,
        experience_plan=experience_plan,
        fewshot_example=fewshot,
    )

    response = await provider.streaming_llm.ainvoke(prompt)
    return response.content


async def review_draft(
    draft: str,
    experiences: list[Experience],
    provider: LLMProvider,
) -> ReviewResult:
    """4단계: 나열식 패턴 + 할루시네이션 검수"""
    experiences_text = _format_experiences_plain(experiences)
    structured_llm = provider.classification_llm.with_structured_output(ReviewResult)
    return await structured_llm.ainvoke(
        REVIEW_PROMPT.format(draft=draft, experiences=experiences_text)
    )


async def revise_draft_text(
    draft: str,
    feedback: str,
    experiences: list[Experience],
    max_length: int | None,
    provider: LLMProvider,
) -> str:
    """4-1단계: 검수 피드백 기반 수정 (조건부)"""
    experiences_text = _format_experiences_plain(experiences)
    response = await provider.streaming_llm.ainvoke(
        REVISION_PROMPT.format(
            draft=draft,
            feedback=feedback,
            experiences=experiences_text,
            min_length=int(max_length * 0.9) if max_length else 0,
            max_length=max_length or "제한 없음",
        )
    )
    return response.content


async def adjust_length_if_needed(
    draft: str,
    max_length: int,
    provider: LLMProvider,
) -> str:
    """4-2단계: 글자수 보정 (조건부, 최대 2회)"""
    min_length = int(max_length * 0.9)

    for _ in range(2):
        current = len(draft)
        if min_length <= current <= max_length:
            break

        if current > max_length:
            direction = f"{current - max_length}자 초과"
        else:
            direction = f"{min_length - current}자 부족"

        response = await provider.streaming_llm.ainvoke(
            LENGTH_ADJUSTMENT_PROMPT.format(
                current_length=current,
                draft=draft,
                min_length=min_length,
                max_length=max_length,
                direction=direction,
            )
        )
        draft = response.content

    return draft


# ============================================================
# Main Streaming Function
# ============================================================

async def generate_ai_response_stream(
    *,
    db: AsyncSession,
    question_id: UUID,
    user_message: str,
    question_content: str,
    max_length: int | None,
    company: str,
    recruit_notice: str | None,
    experience_ids: list[str] | None,
    qdrant_client: QdrantClient,
    user_id: str,
    llm_provider: LLMProvider | None = None,
) -> AsyncGenerator[str, None]:
    """
    멀티 스텝 AI 응답 스트리밍 생성

    자기소개서 요청 (is_cover_letter_request=True):
        1단계 분류 → 2단계 스토리라인 → 3단계 생성 → 4단계 검수/보정 → 결과 전송

    대화 요청 (is_cover_letter_request=False):
        1단계 분류 → 실시간 스트리밍 응답

    Yields:
        - {"type": "content", "content": "..."} - 스트리밍 콘텐츠
        - {"type": "done", "content": "...", "is_draft": bool} - 완료
        - {"type": "error", "message": "..."} - 에러
    """
    try:
        provider = llm_provider or get_llm_provider()

        # 경험 데이터 조회
        experiences: list[Experience] = []
        if experience_ids:
            experiences = get_experiences_by_ids(qdrant_client, experience_ids, user_id)

        # 1단계: 요청 분류
        classification = await classify_request(
            user_message=user_message,
            question=question_content,
            provider=provider,
        )

        if not classification.is_cover_letter_request:
            # === 대화형 응답: 실시간 스트리밍 ===
            experiences_text = (
                _format_experiences_plain(experiences) if experiences
                else "선택된 경험이 없습니다."
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", CONVERSATION_SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ])
            chain = prompt | provider.streaming_llm

            chat_history_instance = PostgresChatMessageHistory(db=db, question_id=question_id)
            await chat_history_instance.aget_messages()

            chain_with_history = RunnableWithMessageHistory(
                chain,
                lambda _: chat_history_instance,
                input_messages_key="input",
                history_messages_key="chat_history",
            )

            full_content = ""
            async for chunk in chain_with_history.astream(
                {
                    "company": company,
                    "recruit_notice": recruit_notice or "채용공고 정보 없음",
                    "question": question_content,
                    "max_length": max_length or "제한 없음",
                    "experiences": experiences_text,
                    "input": user_message,
                },
                config={"configurable": {"session_id": str(question_id)}},
            ):
                content = chunk.content
                if content:
                    full_content += content
                    yield json.dumps({"type": "content", "content": content}, ensure_ascii=False)

            yield json.dumps(
                {"type": "done", "content": full_content, "is_draft": False},
                ensure_ascii=False,
            )
            return

        # === 자기소개서 초안 생성: 멀티 스텝 파이프라인 ===
        # 각 단계 전 SSE keepalive 주석 전송 (Android 연결 유지용)
        # SSE 스펙상 ':'로 시작하는 주석은 모든 클라이언트가 무시함

        # 2단계: 스토리라인 설계
        yield ": ping\n\n"
        storyline = await design_storyline(
            question=question_content,
            max_length=max_length,
            company=company,
            experiences=experiences,
            provider=provider,
        )

        # 3단계: 초안 생성
        yield ": ping\n\n"
        draft = await generate_draft_text(
            storyline=storyline,
            question_type=classification.question_type,
            question=question_content,
            max_length=max_length,
            company=company,
            recruit_notice=recruit_notice,
            provider=provider,
        )

        # 4단계: 검수
        yield ": ping\n\n"
        review = await review_draft(draft, experiences, provider)

        # 4-1단계: 수정 (나열식/할루시네이션 문제 시)
        if review.has_listing_pattern or review.has_hallucination:
            yield ": ping\n\n"
            draft = await revise_draft_text(
                draft=draft,
                feedback=review.feedback,
                experiences=experiences,
                max_length=max_length,
                provider=provider,
            )

        # 4-2단계: 글자수 보정
        if max_length:
            draft = await adjust_length_if_needed(draft, max_length, provider)

        # 최종 결과 전송
        yield json.dumps({"type": "content", "content": draft}, ensure_ascii=False)
        yield json.dumps(
            {"type": "done", "content": draft, "is_draft": True},
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"generate_ai_response_stream error: {e}", exc_info=True)
        yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
