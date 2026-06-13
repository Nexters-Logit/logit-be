"""Slack error notification module."""

import logging
import traceback
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Request

from src.config import settings

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _format_error_blocks(request: Request, exc: Exception) -> dict:
    """Format error information into Slack Block Kit message."""
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    error_type = type(exc).__name__
    error_msg = str(exc)[:300]

    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb = "".join(tb_lines)
    if len(tb) > 1500:
        tb = "...\n" + tb[-1500:]

    env = settings.ENVIRONMENT.upper()
    emoji = ":rotating_light:" if env == "PRODUCTION" else ":warning:"

    # GET → 쿼리 파라미터, POST/PATCH/PUT → Content-Type + Content-Length
    if request.url.query:
        request_detail = f"쿼리: `{request.url.query}`"
    else:
        content_type = request.headers.get("content-type", "없음")
        content_length = request.headers.get("content-length", "없음")
        request_detail = f"Content-Type: `{content_type}`\nContent-Length: `{content_length}`"

    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} [{env}] 서버 에러 발생",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*:link: 요청 경로*\n`{request.method} {request.url.path}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*:clock3: 발생 시각*\n{timestamp}",
                    },
                ],
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*:name_badge: 에러 타입*\n`{error_type}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*:page_facing_up: 요청 정보*\n{request_detail}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:memo: 에러 메시지*\n```{error_msg}```",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:mag: Traceback*\n```{tb}```",
                },
            },
        ]
    }


def send_error_notification(request: Request, exc: Exception) -> None:
    """Send error notification to Slack."""
    if not settings.SLACK_WEBHOOK_URL:
        return
    try:
        payload = _format_error_blocks(request, exc)
        httpx.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception:
        logger.warning("Failed to send Slack error notification", exc_info=True)
