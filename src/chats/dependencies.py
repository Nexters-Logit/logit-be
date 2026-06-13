"""Chat 도메인 의존성 주입 모듈"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

if TYPE_CHECKING:
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    from .rate_limit import ChatRateLimiter

from src.config import settings


class LLMProvider:
    """LLM 인스턴스를 제공하는 클래스"""

    def __init__(self):
        self._streaming_llm: ChatOpenAI | None = None
        self._classification_llm: ChatOpenAI | None = None
        self._writing_llm: ChatAnthropic | None = None

    @property
    def streaming_llm(self) -> ChatOpenAI:
        """스트리밍용 LLM (lazy initialization)"""
        from langchain_openai import ChatOpenAI

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
        from langchain_openai import ChatOpenAI

        if self._classification_llm is None:
            self._classification_llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                streaming=False,
                temperature=0,
            )
        return self._classification_llm

    @property
    def writing_llm(self) -> ChatAnthropic:
        """글쓰기용 LLM - Claude (초안 생성, 수정, 길이 보정)"""
        from langchain_anthropic import ChatAnthropic

        if self._writing_llm is None:
            self._writing_llm = ChatAnthropic(
                model=settings.ANTHROPIC_MODEL,
                api_key=settings.ANTHROPIC_API_KEY,
                temperature=settings.OPENAI_TEMPERATURE,
            )
        return self._writing_llm


@lru_cache
def get_llm_provider() -> LLMProvider:
    """싱글톤 LLMProvider 인스턴스 반환"""
    return LLMProvider()


# FastAPI Dependency
LLMDep = Annotated[LLMProvider, Depends(get_llm_provider)]


# Rate Limiter Dependency
async def get_rate_limiter():
    """ChatRateLimiter 인스턴스 반환"""
    from src.database import get_redis

    from .rate_limit import ChatRateLimiter

    redis = await get_redis()
    return ChatRateLimiter(redis)


RateLimiterDep = Annotated["ChatRateLimiter", Depends(get_rate_limiter)]
