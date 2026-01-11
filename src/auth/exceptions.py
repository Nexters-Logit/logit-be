"""Auth domain-specific exceptions."""

from fastapi import HTTPException, status


class OAuthError(HTTPException):
    """OAuth authentication error."""

    def __init__(self, detail: str = "OAuth authentication failed"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class InvalidTokenError(HTTPException):
    """Invalid or expired token."""

    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class OAuthProviderNotConfiguredError(HTTPException):
    """OAuth provider not configured."""

    def __init__(self, provider: str):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{provider} OAuth not configured",
        )
