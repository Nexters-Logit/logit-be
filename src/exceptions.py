"""
Global shared exceptions.

도메인 공통으로 사용되는 예외 클래스.
도메인 전용 예외는 각 도메인의 exceptions.py에 정의합니다.
(예: src/auth/exceptions.py)
"""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """JWT 인증 실패 (토큰 무효/만료/미제공)."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class UserNotFoundError(HTTPException):
    """사용자를 찾을 수 없음."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class ForbiddenError(HTTPException):
    """리소스 접근 권한 없음 (인증은 됐지만 본인 리소스가 아님)."""

    def __init__(self, detail: str = "Access to this resource is forbidden."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class InactiveUserError(HTTPException):
    """비활성 사용자."""

    def __init__(self, detail: str = "Inactive user"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
