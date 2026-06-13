"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel

# Set test environment variables before importing app
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("MCP_JWT_SECRET", "test-mcp-jwt-secret")

from src.database import get_async_db
from src.main import app

_DB_PATH = "/tmp/logit_test.db"
_SYNC_URL = f"sqlite:///{_DB_PATH}"
_ASYNC_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

_sync_engine = create_engine(_SYNC_URL, connect_args={"check_same_thread": False})
_async_engine = create_async_engine(
    _ASYNC_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)

_tables = [t for t in SQLModel.metadata.sorted_tables if t.name != "chats"]
SQLModel.metadata.create_all(_sync_engine, tables=_tables, checkfirst=True)


def _clear_tables() -> None:
    with _sync_engine.begin() as conn:
        for table in reversed(_tables):
            conn.execute(delete(table))


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    _clear_tables()
    with Session(_sync_engine) as session:
        yield session
    _clear_tables()


@pytest.fixture(autouse=True)
def reset_async_singletons() -> Generator[None, None, None]:
    """Reset Redis/Qdrant singletons so each test gets a fresh connection in the current event loop."""
    import src.database as _db
    _db._redis_client = None
    _db._qdrant_client = None
    yield
    _db._redis_client = None
    _db._qdrant_client = None


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    async def get_async_db_override() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(_async_engine) as async_session:
            yield async_session

    app.dependency_overrides[get_async_db] = get_async_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
