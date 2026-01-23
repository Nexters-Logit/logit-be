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
from .prompts import COVER_LETTER_SYSTEM_PROMPT
from .chat_history import PostgresChatMessageHistory
from .dependencies import LLMProvider, get_llm_provider


# Function Calling 스키마 정의
class DraftClassification(BaseModel):
    """사용자 요청이 자기소개서 초안 작성 요청인지 판단"""

    is_draft: bool = Field(
        description="자기소개서 초안 작성 요청이면 True, 아니면 False. "
                    "True 예시: '써줘', '작성해줘', '만들어줘', '초안', '생성해줘' 등 / "
                    "False 예시: 질문, 피드백 요청, 수정 요청, 일반 대화"
    )


async def classify_draft_intent(
    user_message: str,
    llm_provider: LLMProvider | None = None
) -> bool:
    """Function Calling으로 초안 작성 의도 판단"""

    provider = llm_provider or get_llm_provider()
    llm_with_structured = provider.classification_llm.with_structured_output(DraftClassification)

    result = await llm_with_structured.ainvoke(
        f"다음 사용자 메시지가 자기소개서 초안 작성 요청인지 판단하세요:\n\n{user_message}"
    )

    return result.is_draft


def _format_experience(exp: Experience) -> str:
    """경험을 프롬프트용 텍스트로 변환"""
    return f"""### {exp.title}
- 유형: {exp.experience_type}
- 날짜: {exp.date}
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
    RAG 기반 AI 응답 스트리밍 생성 (RunnableWithMessageHistory 사용)

    Yields:
        JSON 형식의 SSE 데이터
        - {"type": "content", "content": "..."} - 스트리밍 콘텐츠
        - {"type": "done", "content": "전체 내용"} - 완료 시
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

        # 2. 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", COVER_LETTER_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # 3. 체인 구성
        chain = prompt | provider.streaming_llm

        # 4. PostgresChatMessageHistory 인스턴스 생성 및 히스토리 로드
        chat_history_instance = PostgresChatMessageHistory(db=db, question_id=question_id)
        await chat_history_instance.aget_messages()

        # 5. RunnableWithMessageHistory로 체인 래핑
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: chat_history_instance,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        # 6. 스트리밍 응답 생성
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

        # 7. 완료 이벤트
        yield json.dumps({"type": "done", "content": full_content}, ensure_ascii=False)

    except Exception as e:
        yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
