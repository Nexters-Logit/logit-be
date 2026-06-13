from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from src.config import settings


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> str:
    """Create JWT refresh token"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_mcp_token(subject: str | Any, expires_at: datetime | None = None) -> str:
    """
    MCP 서버 전용 JWT 토큰 생성. logit-mcp와 MCP_JWT_SECRET을 공유한다.

    expires_at을 넘기면 구독 만료일을 토큰 만료일로 사용한다.
    """
    if not settings.MCP_JWT_SECRET:
        raise ValueError("MCP_JWT_SECRET is not configured")
    expire = expires_at or (datetime.now(timezone.utc) + timedelta(days=settings.MCP_TOKEN_EXPIRE_DAYS))
    to_encode = {"exp": expire, "sub": str(subject), "type": "mcp"}
    return jwt.encode(to_encode, settings.MCP_JWT_SECRET, algorithm=settings.ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> str | None:
    """
    Verify JWT token and return subject (user_id)
    Returns None if token is invalid
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_sub: str = payload.get("sub")
        token_typ: str = payload.get("type")

        if token_sub is None or token_typ != token_type:
            return None

        return token_sub
    except jwt.InvalidTokenError:
        return None
