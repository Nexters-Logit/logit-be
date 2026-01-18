"""Experience API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from src.common.responses import RESPONSES_CREATE_WITH_AUTH, RESPONSES_CRUD_WITH_AUTH
from src.experience import service
from src.experience.dependencies import QdrantDep
from src.experience.schemas import (
    ExperienceCreate,
    ExperienceListResponse,
    ExperienceRead,
    ExperienceSearchResult,
    ExperienceSearchResponse,
    ExperienceUpdate,
)
from src.users.dependencies import ActiveUser

router = APIRouter()


@router.post(
    "",
    response_model=ExperienceRead,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES_CREATE_WITH_AUTH,
    summary="경험 등록",
    description="STAR 형식으로 새로운 경험을 등록합니다. AI가 자동으로 관련 태그(1~3개)를 생성하고, 임베딩을 생성하여 시맨틱 검색이 가능합니다.",
)
def create_experience(
    experience_create: ExperienceCreate,
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> ExperienceRead:
    """
    Create a new experience with STAR format.

    - **title**: 경험 제목
    - **date**: 경험 발생 날짜 (YYYY-MM-DD)
    - **experience_type**: 경험 타입 (project, work, volunteer 등)
    - **situation**: 상황 (STAR의 S)
    - **task**: 과제 (STAR의 T)
    - **action**: 행동 (STAR의 A)
    - **result**: 결과 (STAR의 R)
    - **category**: 카테고리 (technical, leadership 등)

    AI가 경험 내용을 분석하여 다음 중 1~3개의 태그를 자동으로 생성합니다:
    고객 이해력, 전문성, 소통력, 실행력, 분석력, 문제해결력, 적응력, 책임감
    """
    experience = service.create_experience(
        client=qdrant_client,
        user_id=str(current_user.id),
        experience_create=experience_create,
    )
    return ExperienceRead(**experience.model_dump())


@router.get(
    "",
    response_model=ExperienceListResponse,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 목록 조회",
    description="사용자의 모든 경험을 조회합니다. 페이지네이션을 지원합니다.",
)
def list_experiences(
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
    limit: int = Query(100, ge=1, le=1000, description="페이지당 항목 수"),
    offset: int = Query(0, ge=0, description="오프셋"),
) -> ExperienceListResponse:
    """
    List all experiences for the current user with pagination.

    - **limit**: 페이지당 항목 수 (기본: 100, 최대: 1000)
    - **offset**: 오프셋 (기본: 0)
    """
    experiences, total = service.list_experiences(
        client=qdrant_client,
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
    )

    return ExperienceListResponse(
        experiences=[ExperienceRead(**exp.model_dump()) for exp in experiences],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/search",
    response_model=ExperienceSearchResult,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 검색",
    description="자연어 쿼리로 경험을 시맨틱 검색합니다. 유사도 점수와 함께 결과를 반환합니다.",
)
def search_experiences(
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
    q: str = Query(..., min_length=1, description="검색 쿼리"),
    limit: int = Query(10, ge=1, le=100, description="최대 결과 수"),
) -> ExperienceSearchResult:
    """
    Semantic search for experiences using natural language.

    - **q**: 검색 쿼리 (자연어)
    - **limit**: 최대 결과 수 (기본: 10, 최대: 100)

    Returns experiences ranked by semantic similarity with scores.
    """
    results = service.search_experiences(
        client=qdrant_client,
        user_id=str(current_user.id),
        query=q,
        limit=limit,
    )

    search_responses = [
        ExperienceSearchResponse(
            experience=ExperienceRead(**exp.model_dump()),
            score=score,
        )
        for exp, score in results
    ]

    return ExperienceSearchResult(
        results=search_responses,
        query=q,
        total=len(search_responses),
    )


@router.get(
    "/{experience_id}",
    response_model=ExperienceRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 상세 조회",
    description="특정 경험의 상세 정보를 조회합니다.",
)
def get_experience(
    experience_id: str,
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> ExperienceRead:
    """
    Get a single experience by ID.

    - **experience_id**: 경험 ID (UUID)

    Returns 404 if the experience doesn't exist or doesn't belong to the current user.
    """
    experience = service.get_experience(
        client=qdrant_client,
        experience_id=experience_id,
        user_id=str(current_user.id),
    )

    if not experience:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experience not found",
        )

    return ExperienceRead(**experience.model_dump())


@router.patch(
    "/{experience_id}",
    response_model=ExperienceRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 수정",
    description="기존 경험을 수정합니다. 내용이 변경되면 AI가 태그를 재생성하고 임베딩도 자동으로 재생성됩니다.",
)
def update_experience(
    experience_id: str,
    experience_update: ExperienceUpdate,
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> ExperienceRead:
    """
    Update an existing experience (partial update).

    - **experience_id**: 경험 ID (UUID)
    - **experience_update**: 수정할 필드 (부분 업데이트 지원)

    All fields are optional. Only provided fields will be updated.
    If content (title, situation, task, action, result) changes:
    - AI will regenerate tags automatically
    - Embedding will be regenerated for semantic search

    Raises:
    - 404: Experience not found or doesn't belong to the current user
    """
    experience = service.update_experience(
        client=qdrant_client,
        experience_id=experience_id,
        user_id=str(current_user.id),
        experience_update=experience_update,
    )

    if not experience:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experience not found or could not be updated",
        )

    return ExperienceRead(**experience.model_dump())


@router.delete(
    "/{experience_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 삭제",
    description="경험을 영구적으로 삭제합니다. 삭제 전에 소유권을 확인합니다.",
)
def delete_experience(
    experience_id: str,
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> None:
    """
    Delete an experience permanently.

    - **experience_id**: 경험 ID (UUID)

    Returns:
    - 204 No Content: 삭제 성공

    Raises:
    - 404: Experience not found or doesn't belong to the current user
    - 401: Not authenticated
    - 403: User is not active
    """
    # Service에서 소유권 검증 후 삭제
    # 존재하지 않거나 소유자가 아니면 404 발생
    service.delete_experience(
        client=qdrant_client,
        experience_id=experience_id,
        user_id=str(current_user.id),
    )
