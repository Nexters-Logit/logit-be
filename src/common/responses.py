"""Common API response definitions for OpenAPI documentation."""

from typing import Any

# ============================================================================
# Error Response Definitions (for OpenAPI responses parameter)
# ============================================================================

ERROR_400_BAD_REQUEST: dict[str, Any] = {
    "description": "잘못된 요청 - 요청 형식이 올바르지 않거나 처리할 수 없는 요청",
    "content": {
        "application/json": {
            "example": {"detail": "Bad request."},
        }
    },
}

ERROR_401_UNAUTHORIZED: dict[str, Any] = {
    "description": "인증 실패 - 유효하지 않은 토큰 또는 토큰 없음",
    "content": {
        "application/json": {
            "example": {"detail": "Invalid or missing authentication credentials."},
        }
    },
}

ERROR_403_FORBIDDEN: dict[str, Any] = {
    "description": "권한 없음 - 해당 리소스에 대한 접근 권한이 없음",
    "content": {
        "application/json": {
            "example": {"detail": "Access to this resource is forbidden."},
        }
    },
}

ERROR_404_NOT_FOUND: dict[str, Any] = {
    "description": "리소스 없음 - 요청한 리소스를 찾을 수 없음",
    "content": {
        "application/json": {
            "example": {"detail": "Resource not found."},
        }
    },
}

ERROR_409_CONFLICT: dict[str, Any] = {
    "description": "리소스 충돌 - 이미 존재하는 리소스와 충돌",
    "content": {
        "application/json": {
            "example": {"detail": "Resource already exists."},
        }
    },
}

ERROR_422_VALIDATION_ERROR: dict[str, Any] = {
    "description": "검증 실패 - 요청 데이터의 형식이나 값이 올바르지 않음",
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "email"],
                        "msg": "Invalid email format.",
                        "type": "value_error.email",
                    }
                ]
            },
        }
    },
}

ERROR_500_INTERNAL_SERVER: dict[str, Any] = {
    "description": "서버 오류 - 서버 내부에서 예기치 않은 오류 발생",
    "content": {
        "application/json": {
            "example": {"detail": "Internal server error."},
        }
    },
}

ERROR_501_NOT_IMPLEMENTED: dict[str, Any] = {
    "description": "미구현 - 해당 기능이 아직 구현되지 않음",
    "content": {
        "application/json": {
            "example": {"detail": "This feature is not implemented yet."},
        }
    },
}

ERROR_503_SERVICE_UNAVAILABLE: dict[str, Any] = {
    "description": "서비스 불가 - 일시적으로 서비스를 이용할 수 없음",
    "content": {
        "application/json": {
            "example": {"detail": "Service temporarily unavailable."},
        }
    },
}


# ============================================================================
# Response Combinations (자주 사용되는 조합)
# ============================================================================

# 인증이 필요한 엔드포인트의 공통 에러
RESPONSES_AUTH_REQUIRED: dict[int | str, dict[str, Any]] = {
    401: ERROR_401_UNAUTHORIZED,
    403: ERROR_403_FORBIDDEN,
}

# 기본 CRUD 작업 에러
RESPONSES_CRUD: dict[int | str, dict[str, Any]] = {
    400: ERROR_400_BAD_REQUEST,
    404: ERROR_404_NOT_FOUND,
    422: ERROR_422_VALIDATION_ERROR,
}

# 인증 + CRUD 조합 (목록/상세 조회, 수정, 삭제)
RESPONSES_CRUD_WITH_AUTH: dict[int | str, dict[str, Any]] = {
    **RESPONSES_AUTH_REQUIRED,
    **RESPONSES_CRUD,
}

# 생성 작업 에러
RESPONSES_CREATE: dict[int | str, dict[str, Any]] = {
    400: ERROR_400_BAD_REQUEST,
    409: ERROR_409_CONFLICT,
    422: ERROR_422_VALIDATION_ERROR,
}

# 인증 + 생성 조합
RESPONSES_CREATE_WITH_AUTH: dict[int | str, dict[str, Any]] = {
    **RESPONSES_AUTH_REQUIRED,
    **RESPONSES_CREATE,
}

# 모든 공통 에러 (서버 에러 포함)
RESPONSES_COMMON: dict[int | str, dict[str, Any]] = {
    400: ERROR_400_BAD_REQUEST,
    401: ERROR_401_UNAUTHORIZED,
    403: ERROR_403_FORBIDDEN,
    404: ERROR_404_NOT_FOUND,
    422: ERROR_422_VALIDATION_ERROR,
    500: ERROR_500_INTERNAL_SERVER,
}


# ============================================================================
# Helper Functions
# ============================================================================


def create_responses(
    *response_dicts: dict[int | str, dict[str, Any]],
) -> dict[int | str, dict[str, Any]]:
    """
    여러 응답 딕셔너리를 병합하여 하나의 응답 딕셔너리를 생성합니다.

    사용 예시:
        @router.get(
            "/users/{user_id}",
            responses=create_responses(
                RESPONSES_AUTH_REQUIRED,
                {404: ERROR_404_NOT_FOUND},
            )
        )
    """
    result: dict[int | str, dict[str, Any]] = {}
    for resp_dict in response_dicts:
        result.update(resp_dict)
    return result
