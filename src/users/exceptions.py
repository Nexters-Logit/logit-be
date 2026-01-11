"""Users domain-specific exceptions."""

from fastapi import HTTPException, status


class UserNotFoundError(HTTPException):
    """User not found exception."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class UserAlreadyExistsError(HTTPException):
    """User already exists exception."""

    def __init__(self, email: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {email} already exists",
        )


class InactiveUserError(HTTPException):
    """Inactive user exception."""

    def __init__(self, detail: str = "User is inactive"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
