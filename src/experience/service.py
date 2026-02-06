"""Experience business logic."""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import settings
from src.experience.models import Experience, ExperienceFormatType
from src.experience.schemas import (
    ExperienceCreate,
    ExperienceUpdate,
)
from src.projects.models import Project
from src.questions.models import Question

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _generate_embedding(text: str) -> list[float]:
    """
    Generate embedding vector using OpenAI text-embedding-3-small.

    Args:
        text: Text to embed

    Returns:
        1536-dimensional embedding vector
    """
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def _combine_text_for_embedding(experience: Experience) -> str:
    """
    Combine experience fields into a single text for embedding.

    Args:
        experience: Experience object

    Returns:
        Combined text string
    """
    base_text = f"제목: {experience.title}\n"

    if experience.format_type == ExperienceFormatType.STAR:
        return (
            base_text
            + f"상황: {experience.situation}\n"
            f"과제: {experience.task}\n"
            f"행동: {experience.action}\n"
            f"결과: {experience.result}"
        )
    elif experience.format_type == ExperienceFormatType.PSI:
        return (
            base_text
            + f"문제: {experience.problem}\n"
            f"해결책: {experience.solution}\n"
            f"인사이트: {experience.insight}"
        )
    elif experience.format_type == ExperienceFormatType.FREE:
        return base_text + f"내용: {experience.content}"
    else:
        # Fallback to title only
        return base_text


def _generate_tags(experience: Experience) -> str:
    """
    Generate relevant tags using AI based on experience content.

    Args:
        experience: Experience object

    Returns:
        Comma-separated string of 1-3 tags

    Raises:
        HTTPException: If tag generation fails
    """
    available_tags = [
        "문서작성", "일정관리", "요구사항정의", "프로세스개선", "데이터분석", "커뮤니케이션", "리서치", "문제해결", "협업도구(Notion/Jira/Slack)",
        "프론트엔드", "백엔드", "앱개발", "인프라/클라우드", "DB설계", "트러블슈팅", "API연동", "AI/LLM", "코드리뷰", "시스템아키텍처",
        "UX/UI", "브랜딩", "그래픽디자인", "프로토타이핑", "디자인시스템", "영상편집", "모션그래픽", "3D모델링", "사용자테스트(UT)",
        "서비스기획", "PM/PO", "사업개발", "전략기획", "시장분석", "지표설정(KPI/OKR)", "밴치마킹", "수익모델설계",
        "콘텐츠제작", "퍼포먼스마케팅", "SNS운영", "광고집행", "검색최적화(SEO)", "CRM", "B2B/B2C영업", "제안서작성",
        "고객응대(CS/CX)", "서비스운영", "QA/테스트", "인사/채용", "조직문화", "재무/회계", "이벤트기획"
    ]

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

    prompt = f"""다음 경험 내용을 분석하여 가장 관련성 높은 태그를 선택해주세요.

경험 내용:
{content}

선택 가능한 태그:
{', '.join(available_tags)}

요구사항:
1. 경험 내용과 가장 관련성 높은 태그를 1~3개 선택
2. 선택한 태그를 쉼표로 구분하여 반환
3. 태그 이름만 정확히 반환 (추가 설명 없이)
4. 예시: "벡엔드, DB설계, 트러블슈팅"

선택한 태그:"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 경험을 분석하여 핵심 역량 태그를 추출하는 전문가입니다. 주어진 태그 중에서만 선택하고, 정확히 쉼표로 구분된 형식으로 반환합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=50,
        )

        tags = response.choices[0].message.content.strip()

        # Validate that returned tags are from available tags
        selected_tags = [tag.strip() for tag in tags.split(",")]
        valid_tags = [tag for tag in selected_tags if tag in available_tags]

        # Ensure 1-3 tags
        if not valid_tags:
            # Fallback: use first available tag
            return available_tags[0]
        elif len(valid_tags) > 3:
            valid_tags = valid_tags[:3]

        return ", ".join(valid_tags)

    except Exception as e:
        # Fallback: return default tag if AI fails
        return "전문성"


def create_experience(
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
    # Create temporary Experience object for tag generation
    temp_experience = Experience(
        id=str(uuid4()),
        user_id=user_id,
        **experience_create.model_dump(),
        tags="",  # Will be generated
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    # Generate tags using AI
    tags = _generate_tags(temp_experience)

    # Create final Experience object with tags
    experience = Experience(
        id=temp_experience.id,
        user_id=user_id,
        **experience_create.model_dump(),
        tags=tags,
        created_at=temp_experience.created_at,
        updated_at=temp_experience.updated_at,
    )

    # Generate embedding
    try:
        text = _combine_text_for_embedding(experience)
        embedding = _generate_embedding(text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embedding: {str(e)}",
        )

    # Store in Qdrant
    point = PointStruct(
        id=experience.id,
        vector=embedding,
        payload=experience.model_dump(mode="json"),
    )

    client.upsert(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points=[point],
    )

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
    # Retrieve from Qdrant
    points = client.retrieve(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        ids=[experience_id],
    )

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

    # Scroll to get all matching points
    scroll_result = client.scroll(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        scroll_filter=user_filter,
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )

    points, next_offset = scroll_result

    # Convert to Experience objects
    experiences = [Experience(**point.payload) for point in points]

    # Get total count (approximate, Qdrant doesn't have exact count with filter)
    # We'll count by scrolling all
    count_result = client.scroll(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        scroll_filter=user_filter,
        limit=10000,  # Large limit to get all
        with_payload=False,
        with_vectors=False,
    )
    total = len(count_result[0])

    return experiences, total


def update_experience(
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
    updated_experience = existing.model_copy(update=update_data)
    updated_experience.updated_at = datetime.utcnow()

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
        # Regenerate tags using AI
        updated_experience.tags = _generate_tags(updated_experience)

        # Regenerate embedding
        try:
            text = _combine_text_for_embedding(updated_experience)
            embedding = _generate_embedding(text)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate embedding: {str(e)}",
            )

        # Update with new embedding
        point = PointStruct(
            id=experience_id,
            vector=embedding,
            payload=updated_experience.model_dump(mode="json"),
        )
        client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[point],
        )
    else:
        # Update payload only
        client.set_payload(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            payload=updated_experience.model_dump(mode="json"),
            points=[experience_id],
        )

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
    client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=[experience_id],
    )


def search_experiences(
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
    try:
        query_embedding = _generate_embedding(query)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}",
        )

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
    search_result = client.query_points(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query=query_embedding,
        query_filter=user_filter,
        limit=limit,
        with_payload=True,
    ).points

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
) -> list[tuple[Experience, float]]:
    """
    Get all user experiences with similarity scores against a specific question and its project.

    Args:
        client: Qdrant client
        session: Database session
        user_id: Owner user ID
        question_id: Question ID to match against

    Returns:
        List of tuples (Experience, similarity_score) sorted by score descending

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

    # Generate query embedding
    try:
        query_embedding = _generate_embedding(query_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}",
        )

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
    search_result = client.query_points(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query=query_embedding,
        query_filter=user_filter,
        limit=10000,  # Large limit to get all experiences
        with_payload=True,
    ).points

    # Convert to (Experience, score) tuples
    results = [
        (Experience(**point.payload), point.score)
        for point in search_result
    ]

    # Results are already sorted by score descending from Qdrant
    return results
