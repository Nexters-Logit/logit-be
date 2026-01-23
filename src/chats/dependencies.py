"""Chat 도메인 의존성 주입 모듈"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from langchain_openai import ChatOpenAI

from src.config import settings


class LLMProvider:
    """LLM 인스턴스를 제공하는 클래스"""

    def __init__(self):
        self._streaming_llm: ChatOpenAI | None = None
        self._classification_llm: ChatOpenAI | None = None

    @property
    def streaming_llm(self) -> ChatOpenAI:
        """스트리밍용 LLM (lazy initialization)"""
        if self._streaming_llm is None:
            self._streaming_llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                streaming=True,
                temperature=settings.OPENAI_TEMPERATURE,
            )
        return self._streaming_llm

    @property
    def classification_llm(self) -> ChatOpenAI:
        """분류용 LLM (비스트리밍, 낮은 temperature)"""
        if self._classification_llm is None:
            self._classification_llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                streaming=False,
                temperature=0,
            )
        return self._classification_llm


@lru_cache
def get_llm_provider() -> LLMProvider:
    """싱글톤 LLMProvider 인스턴스 반환"""
    return LLMProvider()


# FastAPI Dependency
LLMDep = Annotated[LLMProvider, Depends(get_llm_provider)]
