"""Pytest configuration and fixtures."""

import os
import pytest
from collections.abc import Generator
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Set test environment variables before importing app
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from src.database import get_async_db
from src.main import app


# In-memory SQLite for testing
@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Create a clean database session for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with dependency override."""

    async def get_async_db_override():
        yield session

    app.dependency_overrides[get_async_db] = get_async_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
