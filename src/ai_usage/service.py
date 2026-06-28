"""AI 사용 로그 기록 서비스 — fire-and-forget 비동기 로깅."""

import asyncio
import logging
from uuid import UUID

from .models import AIUsageLog

logger = logging.getLogger(__name__)


async def _write_log(user_id: UUID, subscription_type: str, plan: str,
                     endpoint: str, model: str | None,
                     input_tokens: int | None, output_tokens: int | None) -> None:
    from src.database import async_session_factory
    try:
        async with async_session_factory() as session:
            session.add(AIUsageLog(
                user_id=user_id,
                subscription_type=subscription_type,
                plan=plan,
                endpoint=endpoint,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ))
            await session.commit()
    except Exception as e:
        logger.warning("AI usage log 기록 실패 (무시): %s", e)


def log_usage(
    *,
    user_id: UUID,
    subscription_type: str,
    plan: str,
    endpoint: str,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """
    AI 사용 로그를 fire-and-forget으로 기록한다.

    별도 DB 세션을 생성하므로 호출자의 세션 트랜잭션과 독립적이다.
    실패해도 예외를 상위로 전파하지 않는다.
    """
    asyncio.create_task(_write_log(
        user_id=user_id,
        subscription_type=subscription_type,
        plan=plan,
        endpoint=endpoint,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    ))
