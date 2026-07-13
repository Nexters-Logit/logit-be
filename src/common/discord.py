"""Discord error notification module."""

import logging
import traceback
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Request

from src.config import settings

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_COLOR_ERROR = 0xFF4444    # 프로덕션 에러 — 빨강
_COLOR_WARNING = 0xFF9900  # dev 에러 — 주황


def _format_error_embed(request: Request, exc: Exception) -> dict:
    """Format error information into Discord embed."""
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    now_utc = datetime.now(timezone.utc).isoformat()
    error_type = type(exc).__name__
    error_msg = str(exc)[:1000]

    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb = "".join(tb_lines)
    if len(tb) > 900:
        tb = "...\n" + tb[-900:]

    env = settings.ENVIRONMENT.upper()
    is_prod = env == "PRODUCTION"
    color = _COLOR_ERROR if is_prod else _COLOR_WARNING
    title = f"{'🚨' if is_prod else '⚠️'} [{env}] 서버 에러 발생"

    if request.url.query:
        request_detail = f"`{request.url.query}`"
    else:
        content_type = request.headers.get("content-type", "없음")
        request_detail = f"Content-Type: `{content_type}`"

    return {
        "embeds": [
            {
                "title": title,
                "color": color,
                "timestamp": now_utc,
                "fields": [
                    {
                        "name": "요청 경로",
                        "value": f"`{request.method} {request.url.path}`",
                        "inline": True,
                    },
                    {
                        "name": "발생 시각",
                        "value": timestamp,
                        "inline": True,
                    },
                    {
                        "name": "에러 타입",
                        "value": f"`{error_type}`",
                        "inline": True,
                    },
                    {
                        "name": "요청 정보",
                        "value": request_detail,
                        "inline": True,
                    },
                    {
                        "name": "에러 메시지",
                        "value": f"```{error_msg}```",
                        "inline": False,
                    },
                    {
                        "name": "Traceback",
                        "value": f"```{tb}```",
                        "inline": False,
                    },
                ],
            }
        ]
    }


async def send_error_notification(request: Request, exc: Exception) -> None:
    """Send error notification to Discord."""
    if not settings.DISCORD_WEBHOOK_URL:
        return
    try:
        payload = _format_error_embed(request, exc)
        async with httpx.AsyncClient() as client:
            await client.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception:
        logger.warning("Failed to send Discord error notification", exc_info=True)
