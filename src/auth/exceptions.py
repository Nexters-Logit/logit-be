"""Auth domain exceptions."""

from fastapi import HTTPException, status


class OAuthError(HTTPException):
    """OAuth 인증 흐름 실패 (코드 교환, 사용자 정보 조회 등)."""

    def __init__(self, detail: str = "OAuth authentication failed"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class InvalidTokenError(HTTPException):
    """유효하지 않은 OAuth 제공자 토큰 (Google/Apple ID 토큰 검증 실패)."""

    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class OAuthProviderNotConfiguredError(HTTPException):
    """OAuth 제공자 미설정."""

    def __init__(self, provider: str):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{provider} OAuth is not configured.",
        )
