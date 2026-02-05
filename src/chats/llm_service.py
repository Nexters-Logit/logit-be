import json
from typing import AsyncGenerator
from uuid import UUID

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.experience.models import Experience
from src.experience.service import get_experience
from .prompts import COVER_LETTER_SYSTEM_PROMPT, PLANNING_PROMPT
from .chat_history import PostgresChatMessageHistory
from .dependencies import LLMProvider, get_llm_provider


# Function Calling 스키마 정의
class DraftClassification(BaseModel):
    """텍스트가 자기소개서 초안인지 판단"""

    is_draft: bool = Field(
        description="지원자 관점에서 본인의 경험/역량을 서술한 글이면 True, AI가 사용자에게 말하는 글이면 False"
    )


class FactItem(BaseModel):
    """경험에서 추출한 사실 정보"""
    fact: str = Field(description="사용할 구체적인 사실 (수치, 성과, 역할 등)")
    source: str = Field(description="출처 경험 제목")


class ContentPlan(BaseModel):
    """자기소개서 작성 계획"""
    is_cover_letter_request: bool = Field(
        description="자기소개서 작성/수정 요청이면 True, 단순 질문/피드백 요청이면 False"
    )
    allowed_facts: list[FactItem] = Field(
        default=[],
        description="경험 정보에서 추출한 사용 가능한 사실 목록"
    )


async def classify_draft_response(
    ai_response: str,
    llm_provider: LLMProvider | None = None
) -> bool:
    """Function Calling으로 AI 응답이 자기소개서 초안인지 판단"""

    provider = llm_provider or get_llm_provider()
    llm_with_structured = provider.classification_llm.with_structured_output(DraftClassification)

    result = await llm_with_structured.ainvoke(
        "이 텍스트의 화자가 누구인지 판단하세요:\n"
        "- 지원자가 본인의 경험을 서술하는 글 → True\n"
        "- AI가 사용자에게 설명/제안/피드백하는 글 → False\n\n"
        f"{ai_response[:500]}"
    )

    return result.is_draft


async def plan_content(
    *,
    user_message: str,
    question_content: str,
    max_length: int | None,
    experiences_text: str,
    llm_provider: LLMProvider | None = None,
) -> ContentPlan:
    """
    계획 단계: 사용자 요청을 분석하고 사용할 경험/사실 추출

    자기소개서 작성 요청이 아니면 빈 계획 반환
    """
    provider = llm_provider or get_llm_provider()
    llm_with_structured = provider.classification_llm.with_structured_output(ContentPlan)

    prompt = PLANNING_PROMPT.format(
        user_message=user_message,
        question=question_content,
        max_length=max_length or "제한 없음",
        experiences=experiences_text,
    )

    result = await llm_with_structured.ainvoke(prompt)
    return result


def _format_experience(exp: Experience) -> str:
    """경험을 프롬프트용 텍스트로 변환"""
    return f"""### {exp.title}
- 유형: {exp.experience_type}
- 날짜: {exp.start_date} ~ {exp.end_date}
- 상황(S): {exp.situation}
- 과제(T): {exp.task}
- 행동(A): {exp.action}
- 결과(R): {exp.result}
- 카테고리: {exp.category}
- 태그: {exp.tags}
"""

def get_experiences_by_ids(
    qdrant_client: QdrantClient,
    experience_ids: list[str],
    user_id: str
) -> list[Experience]:
    """experience_ids로 경험 목록 조회"""
    experiences = []
    for exp_id in experience_ids:
        try:
            exp = get_experience(qdrant_client, exp_id, user_id)
            experiences.append(exp)
        except Exception:
            # 경험을 찾지 못해도 계속 진행
            continue
    return experiences


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
    2단계 할루시네이션 방지 AI 응답 스트리밍 생성

    1단계: 계획 - Function Calling으로 사용할 경험/사실 추출
    2단계: 생성 - 계획된 정보만 사용하여 스트리밍 생성

    Yields:
        JSON 형식의 SSE 데이터
        - {"type": "content", "content": "..."} - 스트리밍 콘텐츠
        - {"type": "done", "content": "..."} - 완료 시
        - {"type": "error", "message": "..."} - 에러 시
    """
    try:
        # 0. LLM Provider 초기화
        provider = llm_provider or get_llm_provider()

        # 1. 경험 정보 조회
        experiences_text = "선택된 경험이 없습니다."
        if experience_ids:
            experiences = get_experiences_by_ids(
                qdrant_client, experience_ids, user_id
            )
            if experiences:
                experiences_text = "\n".join(
                    _format_experience(exp) for exp in experiences
                )

        # 2. [계획 단계] 사용할 경험/사실 추출
        content_plan = await plan_content(
            user_message=user_message,
            question_content=question_content,
            max_length=max_length,
            experiences_text=experiences_text,
            llm_provider=provider,
        )

        # 허용된 사실 목록을 텍스트로 변환
        allowed_facts_text = ""
        if content_plan.is_cover_letter_request and content_plan.allowed_facts:
            allowed_facts_text = "\n".join(
                f"- {fact.fact} (출처: {fact.source})"
                for fact in content_plan.allowed_facts
            )
        else:
            allowed_facts_text = "제한 없음 (자기소개서 작성 요청이 아님)"

        # 3. 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", COVER_LETTER_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # 4. 체인 구성
        chain = prompt | provider.streaming_llm

        # 5. PostgresChatMessageHistory 인스턴스 생성 및 히스토리 로드
        chat_history_instance = PostgresChatMessageHistory(db=db, question_id=question_id)
        await chat_history_instance.aget_messages()

        # 6. RunnableWithMessageHistory로 체인 래핑
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: chat_history_instance,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        # 7. [생성 단계] 스트리밍 응답 생성
        full_content = ""
        async for chunk in chain_with_history.astream(
            {
                "company": company,
                "recruit_notice": recruit_notice or "채용공고 정보 없음",
                "question": question_content,
                "max_length": max_length or "제한 없음",
                "experiences": experiences_text,
                "allowed_facts": allowed_facts_text,
                "input": user_message,
            },
            config={"configurable": {"session_id": str(question_id)}},
        ):
            content = chunk.content
            if content:
                full_content += content
                yield json.dumps({"type": "content", "content": content}, ensure_ascii=False)

        # 8. 완료 이벤트
        yield json.dumps({"type": "done", "content": full_content}, ensure_ascii=False)

    except Exception as e:
        yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
