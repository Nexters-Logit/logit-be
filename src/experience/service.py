"""Experience business logic."""

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

from src.config import settings
from src.experience.models import Experience
from src.experience.schemas import ExperienceCreate, ExperienceUpdate

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
    return (
        f"제목: {experience.title}\n"
        f"상황: {experience.situation}\n"
        f"과제: {experience.task}\n"
        f"행동: {experience.action}\n"
        f"결과: {experience.result}"
    )


def create_experience(
    client: QdrantClient,
    user_id: str,
    experience_create: ExperienceCreate,
) -> Experience:
    """
    Create a new experience with embedding.

    Args:
        client: Qdrant client
        user_id: Owner user ID
        experience_create: Experience creation data

    Returns:
        Created Experience object

    Raises:
        HTTPException: If OpenAI API fails
    """
    # Create Experience object
    experience = Experience(
        id=str(uuid4()),
        user_id=user_id,
        **experience_create.model_dump(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
    Update an existing experience.

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

    # Check if content changed (need to regenerate embedding)
    content_fields = {"title", "situation", "task", "action", "result"}
    content_changed = any(field in update_data for field in content_fields)

    if content_changed:
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
    search_result = client.search(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query_vector=query_embedding,
        query_filter=user_filter,
        limit=limit,
        with_payload=True,
    )

    # Convert to (Experience, score) tuples
    results = [
        (Experience(**point.payload), point.score)
        for point in search_result
    ]

    return results
