"""Experience business logic."""

import logging
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

# Initialize logger
logger = logging.getLogger(__name__)

from src.config import settings
from src.experience.models import (
    AVAILABLE_CATEGORIES,
    AVAILABLE_TAGS,
    Experience,
    ExperienceCategory,
    ExperienceFormatType,
)
from src.experience.schemas import (
    ExperienceCreate,
    ExperienceUpdate,
)
from src.projects.models import Project
from src.questions.models import Question

# Initialize OpenAI async client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _sanitize_for_logging(text: str, max_length: int = 50) -> str:
    """
    Sanitize text for safe logging by truncating and adding ellipsis.
    Prevents PII leakage in logs.

    Args:
        text: Text to sanitize
        max_length: Maximum length to keep (default: 50)

    Returns:
        Sanitized text safe for logging
    """
    if not text:
        return "[empty]"
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


async def _generate_embedding(text: str) -> list[float]:
    """
    Generate embedding vector using OpenAI text-embedding-3-small.

    Args:
        text: Text to embed

    Returns:
        1536-dimensional embedding vector

    Raises:
        HTTPException: If embedding generation fails
    """
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
    except AuthenticationError as e:
        logger.error("OpenAI API authentication failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI API authentication failed. Please check API key configuration.",
        ) from e
    except RateLimitError as e:
        logger.warning("OpenAI API rate limit exceeded: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI API rate limit exceeded. Please try again later.",
        ) from e
    except APIConnectionError as e:
        logger.error("Failed to connect to OpenAI API: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to OpenAI API. Please try again later.",
        ) from e
    except APIError as e:
        logger.error("OpenAI API error while generating embedding: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI API error occurred while generating embedding.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error generating embedding: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while generating embedding.",
        ) from e


def _combine_text_for_embedding(experience: Experience) -> str:
    """
    Combine experience fields into a single text for embedding.
    Filters out None values to prevent "field: None" strings in embeddings.

    Args:
        experience: Experience object

    Returns:
        Combined text string
    """
    parts = [f"제목: {experience.title}"]

    if experience.format_type == ExperienceFormatType.STAR:
        if experience.situation:
            parts.append(f"상황: {experience.situation}")
        if experience.task:
            parts.append(f"과제: {experience.task}")
        if experience.action:
            parts.append(f"행동: {experience.action}")
        if experience.result:
            parts.append(f"결과: {experience.result}")
    elif experience.format_type == ExperienceFormatType.PSI:
        if experience.problem:
            parts.append(f"문제: {experience.problem}")
        if experience.solution:
            parts.append(f"해결책: {experience.solution}")
        if experience.insight:
            parts.append(f"인사이트: {experience.insight}")
    elif experience.format_type == ExperienceFormatType.FREE:
        if experience.content:
            parts.append(f"내용: {experience.content}")

    return "\n".join(parts)


async def _generate_tags_and_category(experience: Experience) -> tuple[str, ExperienceCategory]:
    """
    Generate relevant tags and category using a single AI call based on experience content.

    Args:
        experience: Experience object

    Returns:
        Tuple of (comma-separated tags string, ExperienceCategory)
    """
    available_tags = AVAILABLE_TAGS

    # Build experience content based on format type
    if experience.format_type == ExperienceFormatType.STAR:
        content = f"""제목: {experience.title}
상황: {experience.situation}
과제: {experience.task}
행동: {experience.action}
결과: {experience.result}"""
    elif experience.format_type == ExperienceFormatType.PSI:
        content = f"""제목: {experience.title}
문제: {experience.problem}
해결책: {experience.solution}
인사이트: {experience.insight}"""
    elif experience.format_type == ExperienceFormatType.FREE:
        content = f"""제목: {experience.title}
내용: {experience.content}"""
    else:
        content = f"제목: {experience.title}"

    prompt = f"""다음 경험 내용을 분석하여 태그와 카테고리를 선택해주세요.

경험 내용:
{content}

선택 가능한 태그:
{', '.join(available_tags)}

선택 가능한 카테고리:
{', '.join(AVAILABLE_CATEGORIES)}

요구사항:
1. 경험 내용과 가장 관련성 높은 태그를 1~3개 선택
2. 경험 내용에서 가장 핵심적인 역량 카테고리를 1개 선택
3. 반드시 아래 형식으로만 반환 (추가 설명 없이):
태그: 태그1, 태그2, 태그3
카테고리: 카테고리명"""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 경험을 분석하여 핵심 역량 태그와 카테고리를 추출하는 전문가입니다. 주어진 목록 중에서만 선택하고, 정확히 지정된 형식으로 반환합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=100,
        )

        result = response.choices[0].message.content.strip()

        # Parse tags
        tags_str = "문제해결"
        category = ExperienceCategory.CREATIVE_PROBLEM_SOLVING  # default fallback
        for line in result.split("\n"):
            line = line.strip()
            if line.startswith("태그:"):
                raw_tags = line[len("태그:"):].strip()
                selected_tags = [tag.strip() for tag in raw_tags.split(",")]
                valid_tags = [tag for tag in selected_tags if tag in available_tags]
                if valid_tags:
                    tags_str = ", ".join(valid_tags[:3])
            elif line.startswith("카테고리:"):
                raw_category = line[len("카테고리:"):].strip()
                if raw_category in AVAILABLE_CATEGORIES:
                    category = ExperienceCategory(raw_category)

        return tags_str, category

    except Exception as e:
        logger.warning(
            "Failed to generate tags/category for experience (ID: %s, format: %s): %s",
            experience.id, experience.format_type, e, exc_info=True
        )
        return "문제해결", ExperienceCategory.CREATIVE_PROBLEM_SOLVING


async def _extract_tags_from_question(question_text: str, project_info: str) -> list[str]:
    """
    Extract relevant tags from question and project information using AI.

    Args:
        question_text: Question content
        project_info: Combined project information (company, job_position, recruit_notice)

    Returns:
        List of relevant tags (1-5 tags)
    """
    prompt = f"""다음 문항과 프로젝트 정보를 분석하여 이 문항에 답하기 위해 필요한 역량/경험 태그를 선택해주세요.

문항: {question_text}

프로젝트 정보:
{project_info}

선택 가능한 태그:
{', '.join(AVAILABLE_TAGS)}

요구사항:
1. 이 문항에 답하기 위해 필요한 역량/경험 태그를 1~5개 선택
2. 선택한 태그를 쉼표로 구분하여 반환
3. 태그 이름만 정확히 반환 (추가 설명 없이)
4. 예시: "백엔드, DB설계, 트러블슈팅, API연동"

선택한 태그:"""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 면접 문항을 분석하여 필요한 핵심 역량 태그를 추출하는 전문가입니다. 주어진 태그 중에서만 선택하고, 정확히 쉼표로 구분된 형식으로 반환합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=100,
        )

        tags = response.choices[0].message.content.strip()

        # Validate that returned tags are from available tags
        selected_tags = [tag.strip() for tag in tags.split(",")]
        valid_tags = [tag for tag in selected_tags if tag in AVAILABLE_TAGS]

        # Ensure 1-5 tags
        if not valid_tags:
            # Fallback: return empty list
            return []
        elif len(valid_tags) > 5:
            valid_tags = valid_tags[:5]

        return valid_tags

    except Exception as e:
        logger.exception(
            "Unexpected error extracting tags from question (question_preview: %s, project_preview: %s): %s",
            _sanitize_for_logging(question_text), _sanitize_for_logging(project_info), e
        )
        # Fallback: return empty list if AI fails
        return []


def _calculate_tag_matching_score(experience_tags: str, question_tags: list[str]) -> float:
    """
    Calculate tag matching score between experience and question.

    Args:
        experience_tags: Comma-separated experience tags
        question_tags: List of question-related tags

    Returns:
        Matching score between 0.0 and 1.0
    """
    if not question_tags or not experience_tags:
        return 0.0

    # Parse experience tags
    exp_tags_set = set(tag.strip() for tag in experience_tags.split(","))
    question_tags_set = set(question_tags)

    # Calculate intersection
    matching_tags = exp_tags_set & question_tags_set

    if not matching_tags:
        return 0.0

    # Score based on proportion of matching tags
    # Use Jaccard similarity: |intersection| / |union|
    union_tags = exp_tags_set | question_tags_set
    return len(matching_tags) / len(union_tags)


async def _extract_category_from_question(question_text: str, project_info: str) -> str | None:
    """
    Extract relevant category from question and project information using AI.

    Args:
        question_text: Question content
        project_info: Combined project information (company, job_position, recruit_notice)

    Returns:
        Matching category string or None
    """
    prompt = f"""다음 문항과 프로젝트 정보를 분석하여 이 문항에서 주로 평가하려는 역량 카테고리를 1개 선택해주세요.

문항: {question_text}

프로젝트 정보:
{project_info}

선택 가능한 카테고리:
{', '.join(AVAILABLE_CATEGORIES)}

요구사항:
1. 이 문항에서 가장 중요하게 평가하려는 역량 카테고리를 1개만 선택
2. 카테고리 이름만 정확히 반환 (추가 설명 없이)
3. 예시: "기술적 전문성"

선택한 카테고리:"""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 채용 문항을 분석하여 평가하려는 핵심 역량 카테고리를 추출하는 전문가입니다. 주어진 카테고리 중에서만 선택하고, 정확히 카테고리 이름만 반환합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=50,
        )

        category = response.choices[0].message.content.strip()

        # Validate that returned category is from available categories
        if category in AVAILABLE_CATEGORIES:
            return category

        return None

    except Exception as e:
        logger.exception(
            "Unexpected error extracting category from question (question_preview: %s, project_preview: %s): %s",
            _sanitize_for_logging(question_text), _sanitize_for_logging(project_info), e
        )
        # Fallback: return None if AI fails
        return None


def _calculate_category_matching_score(experience_category: str, question_category: str | None) -> float:
    """
    Calculate category matching score between experience and question.

    Args:
        experience_category: Experience category
        question_category: Question-related category

    Returns:
        Matching score: 1.0 if match, 0.0 if not
    """
    if not question_category:
        return 0.0

    # Exact match
    if experience_category == question_category:
        return 1.0

    return 0.0


async def create_experience(
    client: QdrantClient,
    user_id: str,
    experience_create: ExperienceCreate,
) -> Experience:
    """
    Create a new experience with embedding and auto-generated tags. Supports all format types (STAR/PSI/FREE).

    Args:
        client: Qdrant client
        user_id: Owner user ID
        experience_create: Experience creation data with format_type

    Returns:
        Created Experience object

    Raises:
        HTTPException: If OpenAI API fails
    """
    now = datetime.utcnow()
    exp_id = str(uuid4())

    # Create temporary Experience object for AI generation
    temp_experience = Experience(
        id=exp_id,
        user_id=user_id,
        **experience_create.model_dump(),
        category=ExperienceCategory.CREATIVE_PROBLEM_SOLVING,  # placeholder
        tags="",  # placeholder
        created_at=now,
        updated_at=now,
    )

    # Generate tags and category using AI (single call)
    tags, category = await _generate_tags_and_category(temp_experience)

    # Create final Experience object with AI-generated tags and category
    experience = Experience(
        id=exp_id,
        user_id=user_id,
        **experience_create.model_dump(),
        category=category,
        tags=tags,
        created_at=now,
        updated_at=now,
    )

    # Generate embedding
    text = _combine_text_for_embedding(experience)
    embedding = await _generate_embedding(text)

    # Store in Qdrant
    try:
        point = PointStruct(
            id=experience.id,
            vector=embedding,
            payload=experience.model_dump(mode="json"),
        )

        client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[point],
        )
    except UnexpectedResponse as e:
        logger.error("Failed to store experience in Qdrant: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to store experience in vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error storing experience: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while storing experience.",
        ) from e

    return experience


def get_experience(
    client: QdrantClient,
    experience_id: str,
    user_id: str,
) -> Experience:
    """
    Get a single experience by ID.

    Args:
        client: Qdrant client
        experience_id: Experience ID
        user_id: Owner user ID for authorization

    Returns:
        Experience object

    Raises:
        HTTPException: If not found or unauthorized
    """
    try:
        # Retrieve from Qdrant
        points = client.retrieve(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            ids=[experience_id],
        )
    except UnexpectedResponse as e:
        logger.error("Failed to retrieve experience from Qdrant (ID: %s): %s", experience_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve experience from vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error retrieving experience (ID: %s): %s", experience_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving experience.",
        ) from e

    if not points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experience not found",
        )

    payload = points[0].payload

    # Verify ownership
    if payload.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experience not found",
        )

    return Experience(**payload)


def list_experiences(
    client: QdrantClient,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Experience], int]:
    """
    List all experiences for a user with pagination.

    Args:
        client: Qdrant client
        user_id: Owner user ID
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        Tuple of (list of experiences, total count)

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
        # Scroll to get matching points for current page
        scroll_result = client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            scroll_filter=user_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        points, _ = scroll_result  # Unpack, ignore next_offset

        # Convert to Experience objects
        experiences = [Experience(**point.payload) for point in points]

        # Get total count using count API (more efficient than scrolling)
        count_result = client.count(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            count_filter=user_filter,
        )
        total = count_result.count

        return experiences, total
    except UnexpectedResponse as e:
        logger.error("Failed to list experiences from Qdrant (user: %s): %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to list experiences from vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error listing experiences (user: %s): %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while listing experiences.",
        ) from e


async def update_experience(
    client: QdrantClient,
    experience_id: str,
    user_id: str,
    experience_update: ExperienceUpdate,
) -> Experience:
    """
    Update an existing experience with auto-regenerated tags. Supports all format types (STAR/PSI/FREE).

    Args:
        client: Qdrant client
        experience_id: Experience ID
        user_id: Owner user ID for authorization
        experience_update: Update data (partial)

    Returns:
        Updated Experience object

    Raises:
        HTTPException: If not found, unauthorized, or update fails
    """
    # Get existing experience
    existing = get_experience(client, experience_id, user_id)

    # Apply updates
    update_data = experience_update.model_dump(exclude_unset=True)

    # Validate format-specific fields based on existing format_type
    if existing.format_type == ExperienceFormatType.STAR:
        invalid_fields = {"problem", "solution", "insight", "content"} & update_data.keys()
        if invalid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"STAR format does not support fields: {', '.join(invalid_fields)}. Only situation, task, action, result are allowed.",
            )
    elif existing.format_type == ExperienceFormatType.PSI:
        invalid_fields = {"situation", "task", "action", "result", "content"} & update_data.keys()
        if invalid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PSI format does not support fields: {', '.join(invalid_fields)}. Only problem, solution, insight are allowed.",
            )
    elif existing.format_type == ExperienceFormatType.FREE:
        invalid_fields = {"situation", "task", "action", "result", "problem", "solution", "insight"} & update_data.keys()
        if invalid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"FREE format does not support fields: {', '.join(invalid_fields)}. Only content is allowed.",
            )

    updated_experience = existing.model_copy(update=update_data)
    updated_experience.updated_at = datetime.utcnow()

    # Validate date range after applying updates (catches partial updates)
    if updated_experience.end_date and updated_experience.start_date > updated_experience.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Check if content changed (need to regenerate embedding and tags)
    # Content fields depend on format type
    if existing.format_type == ExperienceFormatType.STAR:
        content_fields = {"title", "situation", "task", "action", "result"}
    elif existing.format_type == ExperienceFormatType.PSI:
        content_fields = {"title", "problem", "solution", "insight"}
    elif existing.format_type == ExperienceFormatType.FREE:
        content_fields = {"title", "content"}
    else:
        content_fields = {"title"}

    content_changed = any(field in update_data for field in content_fields)

    if content_changed:
        # Regenerate tags and category using AI (single call)
        try:
            tags, category = await _generate_tags_and_category(updated_experience)
            updated_experience.tags = tags
            updated_experience.category = category
        except Exception:
            # Keep existing tags/category if regeneration fails
            pass

        # Regenerate embedding
        text = _combine_text_for_embedding(updated_experience)
        embedding = await _generate_embedding(text)

        # Update with new embedding
        try:
            point = PointStruct(
                id=experience_id,
                vector=embedding,
                payload=updated_experience.model_dump(mode="json"),
            )
            client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=[point],
            )
        except UnexpectedResponse as e:
            logger.error("Failed to update experience in Qdrant (ID: %s): %s", experience_id, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to update experience in vector database. Please try again later.",
            ) from e
        except Exception as e:
            logger.exception("Unexpected error updating experience (ID: %s): %s", experience_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating experience.",
            ) from e
    else:
        # Update payload only
        try:
            client.set_payload(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                payload=updated_experience.model_dump(mode="json"),
                points=[experience_id],
            )
        except UnexpectedResponse as e:
            logger.error("Failed to update experience payload in Qdrant (ID: %s): %s", experience_id, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to update experience in vector database. Please try again later.",
            ) from e
        except Exception as e:
            logger.exception("Unexpected error updating experience payload (ID: %s): %s", experience_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating experience.",
            ) from e

    return updated_experience


def delete_experience(
    client: QdrantClient,
    experience_id: str,
    user_id: str,
) -> None:
    """
    Delete an experience.

    Args:
        client: Qdrant client
        experience_id: Experience ID
        user_id: Owner user ID for authorization

    Raises:
        HTTPException: If not found or unauthorized
    """
    # Verify ownership first
    get_experience(client, experience_id, user_id)

    # Delete from Qdrant
    try:
        client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=[experience_id],
        )
    except UnexpectedResponse as e:
        logger.error("Failed to delete experience from Qdrant (ID: %s): %s", experience_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to delete experience from vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error deleting experience (ID: %s): %s", experience_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while deleting experience.",
        ) from e


async def search_experiences(
    client: QdrantClient,
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[tuple[Experience, float]]:
    """
    Semantic search for experiences using natural language query.

    Args:
        client: Qdrant client
        user_id: Owner user ID
        query: Natural language search query
        limit: Maximum number of results

    Returns:
        List of tuples (Experience, similarity_score)

    Raises:
        HTTPException: If search fails
    """
    # Generate query embedding
    query_embedding = await _generate_embedding(query)

    # Filter by user_id
    user_filter = Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id),
            )
        ]
    )

    # Search
    try:
        search_result = client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=query_embedding,
            query_filter=user_filter,
            limit=limit,
            with_payload=True,
        ).points
    except UnexpectedResponse as e:
        logger.error(
            "Failed to search experiences in Qdrant (user: %s, query_preview: %s): %s",
            user_id, _sanitize_for_logging(query), e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to search experiences in vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error searching experiences (user: %s, query_preview: %s): %s",
            user_id, _sanitize_for_logging(query), e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while searching experiences.",
        ) from e

    # Convert to (Experience, score) tuples
    results = [
        (Experience(**point.payload), point.score)
        for point in search_result
    ]

    return results


async def get_experiences_with_question_similarity(
    client: QdrantClient,
    session: AsyncSession,
    user_id: str,
    question_id: UUID,
    tag_bonus_multiplier: float = 1.0,
    category_bonus_multiplier: float = 0.5,
) -> list[tuple[Experience, float]]:
    """
    Get all user experiences with similarity scores against a specific question and its project.
    Uses embedding similarity as base score, with tag and category matching providing bonuses.

    Args:
        client: Qdrant client
        session: Database session
        user_id: Owner user ID
        question_id: Question ID to match against
        tag_bonus_multiplier: Multiplier for tag matching bonus (default: 1.0, means up to 100% bonus)
        category_bonus_multiplier: Multiplier for category matching bonus (default: 0.5, means 50% bonus)

    Returns:
        List of tuples (Experience, similarity_score) sorted by score descending
        Score calculation: base_score (embedding) + tag_bonus + category_bonus

    Raises:
        HTTPException: If question not found, unauthorized, or search fails
    """
    # Get question from database
    question_statement = (
        select(Question)
        .where(Question.id == question_id)
        .where(Question.user_id == UUID(user_id))
        .where(Question.deleted_at.is_(None))
    )
    question_result = await session.execute(question_statement)
    question = question_result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    # Get project from database
    project_statement = (
        select(Project)
        .where(Project.id == question.project_id)
        .where(Project.user_id == UUID(user_id))
        .where(Project.deleted_at.is_(None))
    )
    project_result = await session.execute(project_statement)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Combine question and project info into query text
    query_text = f"""문항: {question.question}
회사: {project.company}
직무: {project.job_position}
채용공고: {project.recruit_notice}"""

    # Extract relevant tags and category from question and project
    project_info = f"회사: {project.company}\n직무: {project.job_position}\n채용공고: {project.recruit_notice}"
    question_tags = await _extract_tags_from_question(question.question, project_info)
    question_category = await _extract_category_from_question(question.question, project_info)

    # Generate query embedding
    query_embedding = await _generate_embedding(query_text)

    # Filter by user_id
    user_filter = Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id),
            )
        ]
    )

    # Search all experiences with similarity scores
    # Set limit high to get all user experiences
    try:
        search_result = client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=query_embedding,
            query_filter=user_filter,
            limit=10000,  # Large limit to get all experiences
            with_payload=True,
        ).points
    except UnexpectedResponse as e:
        logger.error("Failed to search experiences for question matching in Qdrant (user: %s, question: %s): %s", user_id, question_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to search experiences in vector database. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error searching experiences for question matching (user: %s, question: %s): %s", user_id, question_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while matching experiences with question.",
        ) from e

    # Calculate final scores (base embedding score + tag bonus + category bonus)
    results_with_scores = []
    for point in search_result:
        experience = Experience(**point.payload)
        base_score = point.score  # Embedding similarity (0~1)

        # Calculate tag matching score
        tag_score = _calculate_tag_matching_score(experience.tags, question_tags)
        tag_bonus = tag_score * tag_bonus_multiplier if tag_score > 0 else 0.0

        # Calculate category matching score
        category_score = _calculate_category_matching_score(experience.category, question_category)
        category_bonus = category_score * category_bonus_multiplier if category_score > 0 else 0.0

        # Combine all scores
        final_score = min(base_score + tag_bonus + category_bonus, 1.0)  # Cap at 1.0

        results_with_scores.append((experience, final_score))

    # Sort by final score descending
    results_with_scores.sort(key=lambda x: x[1], reverse=True)

    return results_with_scores
