"""LangChain 콜백 — AI 호출 토큰을 캡처해 ai_usage_logs에 기록한다."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from .service import log_usage

logger = logging.getLogger(__name__)


class TokenUsageCallback(AsyncCallbackHandler):
    """
    LangChain on_llm_end 훅으로 input/output 토큰을 캡처한다.

    사용법:
        cb = TokenUsageCallback(user_id=user_id, subscription_type="logit",
                                plan="lite", endpoint="chat")
        await chain.ainvoke(..., config={"callbacks": [cb]})
    """

    def __init__(
        self,
        *,
        user_id: UUID,
        subscription_type: str,
        plan: str,
        endpoint: str,
    ) -> None:
        super().__init__()
        self.user_id = user_id
        self.subscription_type = subscription_type
        self.plan = plan
        self.endpoint = endpoint

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            input_tokens: int | None = None
            output_tokens: int | None = None
            model_name: str | None = None

            llm_output = response.llm_output or {}

            # OpenAI 형식: token_usage.prompt_tokens / completion_tokens
            usage = llm_output.get("token_usage") or llm_output.get("usage")
            if usage:
                input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")

            # Anthropic via LangChain: usage_metadata on AIMessage
            if input_tokens is None and response.generations:
                for gen_list in response.generations:
                    for gen in gen_list:
                        msg = getattr(gen, "message", None)
                        um = getattr(msg, "usage_metadata", None)
                        if um:
                            input_tokens = um.get("input_tokens")
                            output_tokens = um.get("output_tokens")
                            break
                    if input_tokens is not None:
                        break

            model_name = llm_output.get("model_name") or llm_output.get("model")

            log_usage(
                user_id=self.user_id,
                subscription_type=self.subscription_type,
                plan=self.plan,
                endpoint=self.endpoint,
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            logger.warning("TokenUsageCallback on_llm_end 오류 (무시): %s", e)
