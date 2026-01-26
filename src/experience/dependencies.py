"""Experience dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends
from qdrant_client import QdrantClient

from src.database import get_qdrant_client

# Type alias for Qdrant client dependency
QdrantDep = Annotated[QdrantClient, Depends(get_qdrant_client)]
