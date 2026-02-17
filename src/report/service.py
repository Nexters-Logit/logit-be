"""Report business logic."""

import logging
from collections import Counter

from fastapi import HTTPException, status
from pydantic import ValidationError
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from qdrant_client.http.exceptions import UnexpectedResponse

from src.config import settings
from src.experience.models import Experience

# Initialize logger
logger = logging.getLogger(__name__)


def get_experience_aggregates(
    client: QdrantClient,
    user_id: str,
) -> tuple[dict[str, int], dict[str, int], dict[str, int], int]:
    """
    사용자의 경험을 한 번에 조회하여 타입, 카테고리, 태그별로 집계합니다.

    Args:
        client: Qdrant client
        user_id: 사용자 ID

    Returns:
        Tuple of (타입별 개수, 카테고리별 개수, 태그별 개수, 전체 경험 개수)

    Raises:
        HTTPException: If retrieval fails
    """
    experiences = _get_all_user_experiences(client, user_id)
    total = len(experiences)

    # 타입별로 카운트
    type_counts = Counter(exp.experience_type.value for exp in experiences)

    # 카테고리별로 카운트
    category_counts = Counter(exp.category.value for exp in experiences)

    # 모든 태그를 추출 (쉼표로 구분된 문자열을 파싱)
    all_tags = []
    for exp in experiences:
        if exp.tags:
            # 쉼표로 구분된 태그를 분리하고 공백 제거
            tags = [tag.strip() for tag in exp.tags.split(",") if tag.strip()]
            all_tags.extend(tags)

    # 태그별로 카운트
    tag_counts = Counter(all_tags)

    return dict(type_counts), dict(category_counts), dict(tag_counts), total


def get_experience_type_counts(
    client: QdrantClient,
    user_id: str,
) -> tuple[dict[str, int], int]:
    """
    사용자의 경험을 타입별로 집계합니다.

    Args:
        client: Qdrant client
        user_id: 사용자 ID

    Returns:
        Tuple of (타입별 개수 딕셔너리, 전체 경험 개수)

    Raises:
        HTTPException: If retrieval fails
    """
    experiences = _get_all_user_experiences(client, user_id)

    # 타입별로 카운트
    type_counts = Counter(exp.experience_type.value for exp in experiences)

    return dict(type_counts), len(experiences)


def get_experience_category_counts(
    client: QdrantClient,
    user_id: str,
) -> tuple[dict[str, int], int]:
    """
    사용자의 경험을 카테고리별로 집계합니다.

    Args:
        client: Qdrant client
        user_id: 사용자 ID

    Returns:
        Tuple of (카테고리별 개수 딕셔너리, 전체 경험 개수)

    Raises:
        HTTPException: If retrieval fails
    """
    experiences = _get_all_user_experiences(client, user_id)

    # 카테고리별로 카운트
    category_counts = Counter(exp.category.value for exp in experiences)

    return dict(category_counts), len(experiences)


def get_experience_tag_counts(
    client: QdrantClient,
    user_id: str,
) -> tuple[dict[str, int], int]:
    """
    사용자의 경험을 태그별로 집계합니다.

    Args:
        client: Qdrant client
        user_id: 사용자 ID

    Returns:
        Tuple of (태그별 개수 딕셔너리, 전체 경험 개수)

    Raises:
        HTTPException: If retrieval fails
    """
    experiences = _get_all_user_experiences(client, user_id)

    # 모든 태그를 추출 (쉼표로 구분된 문자열을 파싱)
    all_tags = []
    for exp in experiences:
        if exp.tags:
            # 쉼표로 구분된 태그를 분리하고 공백 제거
            tags = [tag.strip() for tag in exp.tags.split(",") if tag.strip()]
            all_tags.extend(tags)

    # 태그별로 카운트
    tag_counts = Counter(all_tags)

    return dict(tag_counts), len(experiences)


def _get_all_user_experiences(
    client: QdrantClient,
    user_id: str,
) -> list[Experience]:
    """
    사용자의 모든 경험을 조회합니다.

    Args:
        client: Qdrant client
        user_id: 사용자 ID

    Returns:
        List of Experience objects

    Raises:
        HTTPException: If retrieval fails
    """
    # Filter by user_id
    user_filter = Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id),
            )
        ]
    )

    try:
        # Scroll to get all matching points, handling pagination
        all_points = []
        next_page_offset = None

        while True:
            scroll_result = client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                scroll_filter=user_filter,
                limit=10000,
                offset=next_page_offset,
                with_payload=True,
                with_vectors=False,
            )

            points, next_page_offset = scroll_result
            all_points.extend(points)

            # Break if no more pages
            if next_page_offset is None:
                break
    except UnexpectedResponse as e:
        logger.error("Failed to retrieve experiences from Qdrant (user: %s): %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve experiences from vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error retrieving experiences (user: %s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving experiences.",
        ) from e
    else:
        # Convert to Experience objects
        try:
            experiences = [Experience(**point.payload) for point in all_points]
            return experiences
        except ValidationError as e:
            logger.error(
                "Failed to validate experience payload from Qdrant (user: %s): %s. "
                "Point count: %d. First invalid payload: %s",
                user_id,
                e,
                len(all_points),
                all_points[0].payload if all_points else None,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid experience data format in database.",
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error converting experience payloads (user: %s). Point count: %d",
                user_id,
                len(all_points),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while processing experiences.",
            ) from e
