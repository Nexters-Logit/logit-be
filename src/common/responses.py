"""Common API response definitions for OpenAPI documentation."""

from typing import Any

# 개별 에러 응답 정의
ERROR_400_BAD_REQUEST = {
    "description": "잘못된 요청",
    "content": {
        "application/json": {
            "example": {"detail": "Bad request"}
        }
    }
}

ERROR_401_UNAUTHORIZED = {
    "description": "인증 실패",
    "content": {
        "application/json": {
            "example": {"detail": "Could not validate credentials"}
        }
    }
}

ERROR_403_FORBIDDEN = {
    "description": "권한 없음",
    "content": {
        "application/json": {
            "example": {"detail": "Not enough permissions"}
        }
    }
}

ERROR_404_NOT_FOUND = {
    "description": "리소스를 찾을 수 없음",
    "content": {
        "application/json": {
            "example": {"detail": "Resource not found"}
        }
    }
}

ERROR_409_CONFLICT = {
    "description": "리소스 충돌",
    "content": {
        "application/json": {
            "example": {"detail": "Resource already exists"}
        }
    }
}

ERROR_422_VALIDATION_ERROR = {
    "description": "입력값 검증 실패",
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "email"],
                        "msg": "field required",
                        "type": "value_error.missing"
                    }
                ]
            }
        }
    }
}

ERROR_500_INTERNAL_SERVER = {
    "description": "서버 내부 오류",
    "content": {
        "application/json": {
            "example": {"detail": "Internal server error"}
        }
    }
}

ERROR_501_NOT_IMPLEMENTED = {
    "description": "구현되지 않음",
    "content": {
        "application/json": {
            "example": {"detail": "Not implemented"}
        }
    }
}

ERROR_503_SERVICE_UNAVAILABLE = {
    "description": "서비스 이용 불가",
    "content": {
        "application/json": {
            "example": {"detail": "Service temporarily unavailable"}
        }
    }
}


# 자주 사용되는 조합들
RESPONSES_AUTH_REQUIRED = {
    401: ERROR_401_UNAUTHORIZED,
    403: ERROR_403_FORBIDDEN,
}

RESPONSES_CRUD = {
    400: ERROR_400_BAD_REQUEST,
    404: ERROR_404_NOT_FOUND,
    422: ERROR_422_VALIDATION_ERROR,
}

RESPONSES_CRUD_WITH_AUTH = {
    **RESPONSES_AUTH_REQUIRED,
    **RESPONSES_CRUD,
}

RESPONSES_CREATE = {
    400: ERROR_400_BAD_REQUEST,
    409: ERROR_409_CONFLICT,
    422: ERROR_422_VALIDATION_ERROR,
}

RESPONSES_CREATE_WITH_AUTH = {
    **RESPONSES_AUTH_REQUIRED,
    **RESPONSES_CREATE,
}

# 모든 공통 에러 (서버 에러 포함)
RESPONSES_COMMON = {
    400: ERROR_400_BAD_REQUEST,
    401: ERROR_401_UNAUTHORIZED,
    403: ERROR_403_FORBIDDEN,
    404: ERROR_404_NOT_FOUND,
    422: ERROR_422_VALIDATION_ERROR,
    500: ERROR_500_INTERNAL_SERVER,
}


def create_responses(*response_dicts: dict[int | str, dict[str, Any]]) -> dict[int | str, dict[str, Any]]:
    """
    여러 응답 딕셔너리를 병합하여 하나의 응답 딕셔너리를 생성합니다.

    사용 예시:
        @router.get(
            "/users/{user_id}",
            responses=create_responses(
                RESPONSES_AUTH_REQUIRED,
                {404: ERROR_404_NOT_FOUND},
                {200: {"description": "사용자 조회 성공"}}
            )
        )
    """
    result = {}
    for resp_dict in response_dicts:
        result.update(resp_dict)
    return result
