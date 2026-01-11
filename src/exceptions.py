"""
Global exceptions for the application.

Domain-specific exceptions should be in each domain's exceptions.py.
For example:
- app/auth/exceptions.py - Auth domain exceptions
- app/users/exceptions.py - Users domain exceptions
"""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Authentication failed exception."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class UserNotFoundError(HTTPException):
    """User not found exception."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class InvalidCredentialsError(HTTPException):
    """Invalid credentials exception."""

    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class InactiveUserError(HTTPException):
    """Inactive user exception."""

    def __init__(self, detail: str = "User is inactive"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class OAuthError(HTTPException):
    """OAuth authentication error."""

    def __init__(self, detail: str = "OAuth authentication failed"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
