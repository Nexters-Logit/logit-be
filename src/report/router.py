"""Report API 엔드포인트"""

from fastapi import APIRouter

from src.common.responses import RESPONSES_CRUD_WITH_AUTH
from src.experience.dependencies import QdrantDep
from src.report import service
from src.report.schemas import (
    CategoryCount,
    CategoryCountResponse,
    ExperienceSummaryResponse,
    TagCount,
    TagCountResponse,
    TypeCount,
    TypeCountResponse,
)
from src.users.dependencies import ActiveUser

router = APIRouter()


@router.get(
    "/experience-summary",
    response_model=ExperienceSummaryResponse,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 요약 조회 (타입, 카테고리, 태그 통합)",
)
def get_experience_summary(
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> ExperienceSummaryResponse:
    """
    사용자가 보유한 경험을 타입, 카테고리, 태그별로 한 번에 집계하여 반환합니다.

    이 엔드포인트는 세 가지 집계를 한 번의 Qdrant 조회로 처리하여 성능을 최적화합니다.

    **Returns:**
    - **type_counts**: 타입별 개수 목록 (개수 내림차순 정렬)
    - **category_counts**: 카테고리별 개수 목록 (개수 내림차순 정렬)
    - **tag_counts**: 태그별 개수 목록 (개수 내림차순 정렬)
    - **total**: 전체 경험 개수
    """
    type_counts_dict, category_counts_dict, tag_counts_dict, total = service.get_experience_aggregates(
        client=qdrant_client,
        user_id=str(current_user.id),
    )

    # 각 카운트를 개수 내림차순으로 정렬
    sorted_types = sorted(type_counts_dict.items(), key=lambda x: x[1], reverse=True)
    sorted_categories = sorted(category_counts_dict.items(), key=lambda x: x[1], reverse=True)
    sorted_tags = sorted(tag_counts_dict.items(), key=lambda x: x[1], reverse=True)

    type_counts = [TypeCount(type=type_name, count=count) for type_name, count in sorted_types]
    category_counts = [CategoryCount(category=category_name, count=count) for category_name, count in sorted_categories]
    tag_counts = [TagCount(tag=tag_name, count=count) for tag_name, count in sorted_tags]

    return ExperienceSummaryResponse(
        type_counts=type_counts,
        category_counts=category_counts,
        tag_counts=tag_counts,
        total=total,
    )


@router.get(
    "/experience-type-count",
    response_model=TypeCountResponse,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 타입별 개수 조회",
)
def get_experience_type_count(
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> TypeCountResponse:
    """
    사용자가 보유한 경험을 타입별로 집계하여 개수를 반환합니다.

    경험 타입: 아르바이트, 인턴, 정규직, 계약직, 봉사 활동, 수상경력, 동아리 활동, 연구 활동, 군복무, 개인 활동

    **Returns:**
    - **data**: 타입별 개수 목록 (개수 내림차순 정렬)
    - **total**: 전체 경험 개수
    """
    type_counts, total = service.get_experience_type_counts(
        client=qdrant_client,
        user_id=str(current_user.id),
    )

    # 타입을 개수가 많은 순서로 정렬
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)

    data = [
        TypeCount(type=type_name, count=count)
        for type_name, count in sorted_types
    ]

    return TypeCountResponse(data=data, total=total)


@router.get(
    "/experience-category-count",
    response_model=CategoryCountResponse,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 카테고리별 개수 조회",
)
def get_experience_category_count(
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> CategoryCountResponse:
    """
    사용자가 보유한 경험을 카테고리별로 집계하여 개수를 반환합니다.

    경험 카테고리: 고객 가치 지향, 기술적 전문성, 협력적 소통, 주도적 실행력, 논리적 분석력, 창의적 문제해결, 유연한 적응력, 끈기있는 책임감

    **Returns:**
    - **data**: 카테고리별 개수 목록 (개수 내림차순 정렬)
    - **total**: 전체 경험 개수
    """
    category_counts, total = service.get_experience_category_counts(
        client=qdrant_client,
        user_id=str(current_user.id),
    )

    # 카테고리를 개수가 많은 순서로 정렬
    sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

    data = [
        CategoryCount(category=category_name, count=count)
        for category_name, count in sorted_categories
    ]

    return CategoryCountResponse(data=data, total=total)


@router.get(
    "/experience-tag-count",
    response_model=TagCountResponse,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="경험 태그별 개수 조회",
)
def get_experience_tag_count(
    current_user: ActiveUser,
    qdrant_client: QdrantDep,
) -> TagCountResponse:
    """
    사용자가 보유한 경험을 태그별로 집계하여 개수를 반환합니다.

    태그는 AI가 자동으로 생성한 기술/역량 태그입니다.

    **Returns:**
    - **data**: 태그별 개수 목록 (많이 사용된 순서로 정렬 가능)
    - **total**: 전체 경험 개수
    """
    tag_counts, total = service.get_experience_tag_counts(
        client=qdrant_client,
        user_id=str(current_user.id),
    )

    # 태그를 개수가 많은 순서로 정렬
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    data = [TagCount(tag=tag_name, count=count) for tag_name, count in sorted_tags]

    return TagCountResponse(data=data, total=total)
