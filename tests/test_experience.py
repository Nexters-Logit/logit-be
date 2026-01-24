"""Tests for experience domain."""

import datetime as dt
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.experience.models import Experience, ExperienceCategory, ExperienceType
from src.experience.schemas import ExperienceCreate
from src.security import create_access_token
from src.users.models import OAuthProvider, User


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing."""
    return MagicMock()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch("src.experience.service.openai_client") as mock:
        # Mock embedding response
        mock.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        # Mock chat completion response for tags
        mock.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="전문성, 문제해결력, 고객 이해력")
                )
            ]
        )
        yield mock


@pytest.fixture
def test_user(session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        oauth_provider=OAuthProvider.GOOGLE,
        oauth_provider_id="google_test_123",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Create authorization headers for test user."""
    access_token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def sample_experience_data() -> dict:
    """Sample experience data for testing."""
    return {
        "title": "AI 챗봇 서비스 개발",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
        "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
        "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
        "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
        "category": "기술적 전문성",
    }


# Model Tests
def test_experience_model_creation():
    """Test Experience model instantiation."""
    exp = Experience(
        id=str(uuid4()),
        user_id=str(uuid4()),
        title="Test Experience",
        start_date=dt.date(2024, 6, 1),
        end_date=dt.date(2024, 6, 15),
        experience_type=ExperienceType.PROJECT,
        situation="Test situation",
        task="Test task",
        action="Test action",
        result="Test result",
        category=ExperienceCategory.TECHNICAL_PROFICIENCY,
        tags="전문성, 문제해결력",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert exp.title == "Test Experience"
    assert exp.experience_type == ExperienceType.PROJECT
    assert exp.category == ExperienceCategory.TECHNICAL_PROFICIENCY
    assert "전문성" in exp.tags


def test_experience_create_schema():
    """Test ExperienceCreate schema validation."""
    data = {
        "title": "Test",
        "start_date": dt.date(2024, 6, 1),
        "end_date": dt.date(2024, 6, 15),
        "experience_type": ExperienceType.PROJECT,
        "situation": "Situation",
        "task": "Task",
        "action": "Action",
        "result": "Result",
        "category": ExperienceCategory.TECHNICAL_PROFICIENCY,
    }
    schema = ExperienceCreate(**data)
    assert schema.title == "Test"
    assert schema.experience_type == ExperienceType.PROJECT


# API Endpoint Tests
@patch("src.database.get_qdrant_client")
def test_create_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    sample_experience_data: dict,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test creating an experience successfully."""
    mock_get_qdrant.return_value = mock_qdrant_client

    response = client.post(
        "/api/v1/experiences",
        headers=auth_headers,
        json=sample_experience_data,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_experience_data["title"]
    assert data["situation"] == sample_experience_data["situation"]
    assert "tags" in data
    assert "id" in data
    assert "created_at" in data


def test_create_experience_unauthenticated(
    client: TestClient, sample_experience_data: dict
):
    """Test creating experience without authentication."""
    response = client.post("/api/v1/experiences", json=sample_experience_data)
    assert response.status_code == 401


@patch("src.database.get_qdrant_client")
@patch("src.experience.service.openai_client")
def test_create_experience_invalid_data(
    mock_openai, mock_get_qdrant, client: TestClient, auth_headers: dict
):
    """Test creating experience with invalid data."""
    mock_get_qdrant.return_value = MagicMock()
    invalid_data = {
        "title": "",  # Empty title should fail
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
    }
    response = client.post(
        "/api/v1/experiences", headers=auth_headers, json=invalid_data
    )
    assert response.status_code == 422


@patch("src.database.get_qdrant_client")
def test_list_experiences_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
):
    """Test listing experiences."""
    mock_get_qdrant.return_value = mock_qdrant_client

    # Mock scroll response
    mock_point = MagicMock()
    mock_point.payload = {
        "id": str(uuid4()),
        "user_id": str(test_user.id),
        "title": "Test Experience",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "Test situation",
        "task": "Test task",
        "action": "Test action",
        "result": "Test result",
        "category": "technical_proficiency",
        "tags": "전문성, 문제해결력",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.scroll.return_value = ([mock_point], None)

    response = client.get("/api/v1/experiences", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "experiences" in data
    assert "total" in data
    assert data["total"] >= 0
    assert isinstance(data["experiences"], list)


def test_list_experiences_unauthenticated(client: TestClient):
    """Test listing experiences without authentication."""
    response = client.get("/api/v1/experiences")
    assert response.status_code == 401


@patch("src.database.get_qdrant_client")
def test_get_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
):
    """Test getting a single experience."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "Test Experience",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "Test situation",
        "task": "Test task",
        "action": "Test action",
        "result": "Test result",
        "category": "technical_proficiency",
        "tags": "전문성, 문제해결력",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    response = client.get(
        f"/api/v1/experiences/{experience_id}", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == experience_id
    assert data["title"] == "Test Experience"
    assert data["tags"] == "전문성, 문제해결력"


@patch("src.database.get_qdrant_client")
def test_get_experience_not_found(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    mock_qdrant_client: MagicMock,
):
    """Test getting non-existent experience."""
    mock_get_qdrant.return_value = mock_qdrant_client
    mock_qdrant_client.retrieve.return_value = []

    experience_id = str(uuid4())
    response = client.get(
        f"/api/v1/experiences/{experience_id}", headers=auth_headers
    )

    assert response.status_code == 404


@patch("src.database.get_qdrant_client")
def test_update_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test updating an experience."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "Original Title",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "Original situation",
        "task": "Original task",
        "action": "Original action",
        "result": "Original result",
        "category": "기술적 전문성",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    update_data = {"title": "Updated Title", "result": "Updated result"}

    response = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["result"] == "Updated result"


@patch("src.database.get_qdrant_client")
def test_delete_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
):
    """Test deleting an experience."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "To Be Deleted",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    response = client.delete(
        f"/api/v1/experiences/{experience_id}", headers=auth_headers
    )

    assert response.status_code == 204


@patch("src.database.get_qdrant_client")
def test_search_experiences_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test semantic search for experiences."""
    mock_get_qdrant.return_value = mock_qdrant_client

    # Mock search response
    mock_point = MagicMock()
    mock_point.payload = {
        "id": str(uuid4()),
        "user_id": str(test_user.id),
        "title": "AI 챗봇 개발",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "전문성, 문제해결력",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_point.score = 0.92
    mock_qdrant_client.search.return_value = [mock_point]

    response = client.get(
        "/api/v1/experiences/search?q=AI 챗봇", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "query" in data
    assert data["query"] == "AI 챗봇"
    assert len(data["results"]) > 0
    assert data["results"][0]["score"] == 0.92


def test_search_experiences_unauthenticated(client: TestClient):
    """Test search without authentication."""
    response = client.get("/api/v1/experiences/search?q=test")
    assert response.status_code == 401


@patch("src.database.get_qdrant_client")
@patch("src.experience.service.openai_client")
def test_search_experiences_missing_query(
    mock_openai, mock_get_qdrant, client: TestClient, auth_headers: dict
):
    """Test search without query parameter."""
    mock_get_qdrant.return_value = MagicMock()
    response = client.get("/api/v1/experiences/search", headers=auth_headers)
    assert response.status_code == 422


@patch("src.database.get_qdrant_client")
def test_get_other_user_experience_forbidden(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    mock_qdrant_client: MagicMock,
):
    """Test accessing another user's experience."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    other_user_id = str(uuid4())

    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": other_user_id,
        "title": "Other User's Experience",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    response = client.get(
        f"/api/v1/experiences/{experience_id}", headers=auth_headers
    )

    assert response.status_code == 404
