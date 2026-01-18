from collections.abc import AsyncGenerator

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings

# Create async database engine
async_engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=True,
    future=True,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session dependency.
    """
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


# Qdrant client (singleton)
_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """
    Get Qdrant client instance (singleton).
    """
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
    return _qdrant_client


def init_qdrant_collection() -> None:
    """
    Initialize Qdrant collection for embeddings.
    Creates collection if it doesn't exist.
    """
    client = get_qdrant_client()

    # Check if collection exists
    collections = client.get_collections().collections
    collection_exists = any(
        c.name == settings.QDRANT_COLLECTION_NAME for c in collections
    )

    if not collection_exists:
        # Create collection with OpenAI text-embedding-3-small dimensions (1536)
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE,
            ),
        )
        print(f"Created Qdrant collection: {settings.QDRANT_COLLECTION_NAME}")
    else:
        print(f"Qdrant collection already exists: {settings.QDRANT_COLLECTION_NAME}")