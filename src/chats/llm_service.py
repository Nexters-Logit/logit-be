import asyncio
import json
import logging
import re
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
    HALLUCINATION_CHECK_PROMPT,
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
        description="자기소개서 본문을 출력해야 하면 True (신규 작성, 수정, 재작성, 첨삭 모두 포함). 본문 없이 조언/질문 답변만 하면 False"
    )
    is_new_draft: bool = Field(
        description="완전히 새로운 초안 생성 요청이면 True. 기존 초안 수정/보완이면 False"
    )
    question_type: QuestionType = Field(
        description="문항 유형 분류"
    )


class StorylineExperience(BaseModel):
    title: str = Field(description="경험 제목")
    role: str = Field(description="주 경험 / 보조 경험")
    key_facts: list[str] = Field(description="이 경험에서 사용할 핵심 사실 (1~3개)")


class Storyline(BaseModel):
    core_message: str = Field(description="자기소개서의 핵심 메시지 (한 문장)")
    experiences: list[StorylineExperience] = Field(description="경험별 역할 및 사용 계획")


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
    else:  # FREE - 자유 형식: 내용에서 직접 핵심 사실 추출 필요
        if exp.content:
            lines.append(f"- 경험 내용 (자유 형식, 핵심 사실을 직접 추출하세요): {exp.content}")

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


def _check_listing_pattern(draft: str) -> bool:
    """나열식 패턴 감지 (LLM 없이 정규식으로)"""
    patterns = [
        r'첫째[,\s]',
        r'둘째[,\s]',
        r'셋째[,\s]',
        r'첫 번째',
        r'두 번째',
        r'세 번째',
        r'\n[①②③④⑤]',
        r'\n\s*\d+\.',
    ]
    return any(re.search(p, draft) for p in patterns)


async def _check_hallucination(
    draft: str,
    experiences: list[Experience],
    provider: LLMProvider,
) -> bool:
    """할루시네이션 감지 (yes/no LLM, structured output 없이 ~2-3s)"""
    if not experiences:
        return False
    try:
        experiences_text = _format_experiences_plain(experiences)
        response = await provider.classification_llm.ainvoke(
            HALLUCINATION_CHECK_PROMPT.format(
                experiences=experiences_text,
                draft=draft,
            )
        )
        return response.content.strip().lower().startswith("yes")
    except Exception:
        logger.warning("Hallucination check failed, skipping", exc_info=True)
        return False


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
    question: str,
    max_length: int | None,
    company: str,
    recruit_notice: str | None,
    provider: LLMProvider,
) -> str:
    """3단계: 스토리라인 기반 초안 생성 (비스트리밍)"""
    experience_plan = "\n".join(
        f"- [{exp.role}] {exp.title}: {', '.join(exp.key_facts)}"
        for exp in storyline.experiences
    )

    prompt = GENERATION_PROMPT.format(
        company=company,
        recruit_notice=recruit_notice or "채용공고 정보 없음",
        question=question,
        max_length=max_length or "제한 없음",
        min_length=int(max_length * 0.85) if max_length else 0,
        core_message=storyline.core_message,
        experience_plan=experience_plan,
    )

    response = await provider.streaming_llm.ainvoke(prompt)
    return response.content



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
    """4-2단계: 글자수 보정 (조건부, 최대 1회 / 허용 범위 ±15%)"""
    min_length = int(max_length * 0.85)

    for _ in range(1):
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
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run() -> None:
        """파이프라인 전체를 백그라운드 태스크로 실행, 결과를 queue에 전달"""
        try:
            provider = llm_provider or get_llm_provider()

            # 1단계: 요청 분류 + 경험 로딩 병렬 실행
            async def _load_experiences() -> list[Experience]:
                if experience_ids:
                    return await asyncio.to_thread(
                        get_experiences_by_ids, qdrant_client, experience_ids, user_id
                    )
                return []

            classification, experiences = await asyncio.gather(
                classify_request(
                    user_message=user_message,
                    question=question_content,
                    provider=provider,
                ),
                _load_experiences(),
            )

            if not classification.is_new_draft:
                # === 대화형 응답 (수정 요청 포함): 실시간 스트리밍 ===
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
                        await queue.put(json.dumps({"type": "content", "content": content}, ensure_ascii=False))

                await queue.put(json.dumps(
                    {"type": "done", "content": full_content, "is_draft": classification.is_cover_letter_request},
                    ensure_ascii=False,
                ))

            else:
                # === 자기소개서 초안 생성: 멀티 스텝 파이프라인 ===

                # 2단계: 스토리라인 설계
                storyline = await design_storyline(
                    question=question_content,
                    max_length=max_length,
                    company=company,
                    experiences=experiences,
                    provider=provider,
                )

                # 3단계: 초안 생성
                draft = await generate_draft_text(
                    storyline=storyline,
                    question=question_content,
                    max_length=max_length,
                    company=company,
                    recruit_notice=recruit_notice,
                    provider=provider,
                )

                # 4단계: 검수 (정규식 + yes/no LLM 병렬)
                async def _listing_check() -> bool:
                    return _check_listing_pattern(draft)

                has_listing, has_hallucination = await asyncio.gather(
                    _listing_check(),
                    _check_hallucination(draft, experiences, provider),
                )

                feedbacks: list[str] = []
                if has_listing:
                    feedbacks.append(
                        "경험들이 나열식으로 서술되어 있습니다. '첫째~둘째~' 또는 단락별 나열 구조 대신 하나의 자연스러운 이야기 흐름으로 재작성하세요."
                    )
                if has_hallucination:
                    feedbacks.append(
                        "경험 정보에 없는 수치, 성과, 역할, 활동이 포함되어 있습니다. 원본 경험 정보에 있는 사실만 사용하세요."
                    )

                if feedbacks:
                    draft = await revise_draft_text(
                        draft=draft,
                        feedback="\n".join(feedbacks),
                        experiences=experiences,
                        max_length=max_length,
                        provider=provider,
                    )

                # 4-2단계: 글자수 보정
                if max_length:
                    draft = await adjust_length_if_needed(draft, max_length, provider)

                # 청크 단위 스트리밍 (5자씩, 100ms 간격)
                chunk_size = 5
                for i in range(0, len(draft), chunk_size):
                    await queue.put(json.dumps({"type": "content", "content": draft[i:i + chunk_size]}, ensure_ascii=False))
                    await asyncio.sleep(0.1)

                await queue.put(json.dumps(
                    {"type": "done", "content": draft, "is_draft": True},
                    ensure_ascii=False,
                ))

        except Exception as e:
            logger.error(f"generate_ai_response_stream error: {e}", exc_info=True)
            await queue.put(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))
        finally:
            await queue.put(None)  # 완료 신호

    # 파이프라인을 백그라운드 태스크로 시작
    asyncio.create_task(_run())

    # queue에서 결과를 받으며 5초마다 ping 전송 (Android 연결 유지)
    HEARTBEAT_INTERVAL = 5.0
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
            if item is None:
                break
            yield item
        except asyncio.TimeoutError:
            yield json.dumps({"type": "ping"}, ensure_ascii=False)
