"""Authentication utility functions."""

from src.config import settings


def get_oauth_redirect_uri(provider: str) -> str:
    """BACKEND_HOST 기반 OAuth provider 콜백 URL 생성."""
    return f"{settings.BACKEND_HOST.rstrip('/')}{settings.API_V1_STR}/auth/{provider}/callback"


def get_frontend_callback_url() -> str:
    """FRONTEND_HOST 기반 프론트엔드 콜백 URL 생성."""
    return f"{settings.FRONTEND_HOST.rstrip('/')}/auth/callback"
