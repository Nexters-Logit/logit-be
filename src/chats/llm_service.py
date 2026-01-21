import json
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from qdrant_client import QdrantClient

from src.config import settings
from src.experience.models import Experience
from src.experience.service import get_experience
from .models import Chat, ChatRole
from .prompts import COVER_LETTER_SYSTEM_PROMPT


# LLM 초기화
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
    streaming=True,
    temperature=0.7,
)


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


def _format_chat_history(chats: list[Chat]) -> list:
    """채팅 히스토리를 Langchain 메시지 형식으로 변환"""
    messages = []
    for chat in chats:
        if chat.role == ChatRole.USER:
            messages.append(HumanMessage(content=chat.content))
        else:
            messages.append(AIMessage(content=chat.content))
    return messages


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
    user_message: str,
    question_content: str,
    max_length: int | None,
    company: str,
    recruit_notice: str | None,
    experience_ids: list[str] | None,
    chat_history: list[Chat],
    qdrant_client: QdrantClient,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    RAG 기반 AI 응답 스트리밍 생성

    Yields:
        JSON 형식의 SSE 데이터
        - {"type": "content", "content": "..."} - 스트리밍 콘텐츠
        - {"type": "done", "content": "전체 내용"} - 완료 시
        - {"type": "error", "message": "..."} - 에러 시
    """
    try:
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
        chain = prompt | llm

        # 4. 채팅 히스토리 변환
        history_messages = _format_chat_history(chat_history)

        # 5. 스트리밍 응답 생성
        full_content = ""
        async for chunk in chain.astream({
            "company": company,
            "recruit_notice": recruit_notice or "채용공고 정보 없음",
            "question": question_content,
            "max_length": max_length or "제한 없음",
            "experiences": experiences_text,
            "chat_history": history_messages,
            "input": user_message,
        }):
            content = chunk.content
            if content:
                full_content += content
                yield json.dumps({"type": "content", "content": content}, ensure_ascii=False)

        # 6. 완료 이벤트
        yield json.dumps({"type": "done", "content": full_content}, ensure_ascii=False)

    except Exception as e:
        yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
