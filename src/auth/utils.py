"""Authentication utility functions."""

from coolname import generate as coolname_generate

from src.config import settings


def generate_random_nickname() -> str:
    """형용사 + 동물 조합의 랜덤 닉네임 생성 (예: Lucky Fox, Brave Eagle)."""
    words = coolname_generate(2)  # ['lucky', 'fox']
    return " ".join(word.capitalize() for word in words)


def get_oauth_redirect_uri(provider: str) -> str:
    """BACKEND_HOST 기반 OAuth provider 콜백 URL 생성."""
    return f"{settings.BACKEND_HOST.rstrip('/')}{settings.API_V1_STR}/auth/{provider}/callback"


def get_frontend_callback_url() -> str:
    """FRONTEND_HOST 기반 프론트엔드 콜백 URL 생성."""
    return f"{settings.FRONTEND_HOST.rstrip('/')}/auth/callback"
