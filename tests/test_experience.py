"""Tests for experience domain."""

import datetime as dt
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.experience.models import Experience, ExperienceCategory, ExperienceFormatType, ExperienceType
from src.experience.schemas import ExperienceCreate
from src.projects.models import Project
from src.questions.models import Question
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
    """Sample STAR experience data for testing."""
    return {
        "title": "AI 챗봇 서비스 개발",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "format_type": "STAR",
        "situation": "팀 프로젝트에서 사용자 문의 응대 자동화가 필요했습니다.",
        "task": "자연어 처리 기반 챗봇을 설계하고 구현해야 했습니다.",
        "action": "OpenAI API를 활용하여 RAG 기반 챗봇을 개발하고, FastAPI로 REST API를 구축했습니다.",
        "result": "응답 시간을 70% 단축하고 고객 만족도를 85%로 향상시켰습니다.",
        "category": "기술적 전문성",
    }


@pytest.fixture
def sample_psi_experience_data() -> dict:
    """Sample PSI experience data for testing."""
    return {
        "title": "팀 협업 프로세스 개선",
        "start_date": "2024-03-01",
        "end_date": "2024-05-30",
        "experience_type": "정규직",
        "format_type": "PSI",
        "problem": "팀원 간 커뮤니케이션이 원활하지 않아 프로젝트 진행이 지연되었습니다.",
        "solution": "주간 스탠드업 미팅을 도입하고 Notion으로 작업 현황을 실시간 공유했습니다.",
        "insight": "정기적인 소통과 투명한 정보 공유가 팀 생산성을 크게 향상시킨다는 것을 배웠습니다.",
        "category": "협력적 소통",
    }


@pytest.fixture
def sample_free_experience_data() -> dict:
    """Sample free format experience data for testing."""
    return {
        "title": "오픈소스 프로젝트 기여",
        "start_date": "2024-01-10",
        "end_date": "2024-02-20",
        "experience_type": "개인 활동",
        "format_type": "FREE",
        "content": "React 라이브러리의 버그를 발견하고 수정하는 PR을 제출했습니다. 커뮤니티의 피드백을 받아 코드를 개선했고, 최종적으로 메인 브랜치에 머지되었습니다. 이 과정에서 코드 리뷰 문화와 오픈소스 기여 프로세스를 깊이 이해하게 되었습니다.",
        "category": "기술적 전문성",
    }


# Model Tests
def test_experience_model_creation_star():
    """Test STAR format Experience model instantiation."""
    exp = Experience(
        id=str(uuid4()),
        user_id=str(uuid4()),
        title="Test Experience",
        start_date=dt.date(2024, 6, 1),
        end_date=dt.date(2024, 6, 15),
        experience_type=ExperienceType.FULL_TIME,
        format_type=ExperienceFormatType.STAR,
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
    assert exp.experience_type == ExperienceType.FULL_TIME
    assert exp.format_type == ExperienceFormatType.STAR
    assert exp.category == ExperienceCategory.TECHNICAL_PROFICIENCY
    assert "전문성" in exp.tags


def test_experience_model_creation_psi():
    """Test PSI format Experience model instantiation."""
    exp = Experience(
        id=str(uuid4()),
        user_id=str(uuid4()),
        title="PSI Test Experience",
        start_date=dt.date(2024, 3, 1),
        end_date=dt.date(2024, 5, 30),
        experience_type=ExperienceType.FULL_TIME,
        format_type=ExperienceFormatType.PSI,
        problem="Test problem",
        solution="Test solution",
        insight="Test insight",
        category=ExperienceCategory.COLLABORATIVE_COMMUNICATION,
        tags="소통력, 문제해결력",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert exp.title == "PSI Test Experience"
    assert exp.format_type == ExperienceFormatType.PSI
    assert exp.problem == "Test problem"
    assert exp.solution == "Test solution"
    assert exp.insight == "Test insight"


def test_experience_model_creation_free():
    """Test free format Experience model instantiation."""
    exp = Experience(
        id=str(uuid4()),
        user_id=str(uuid4()),
        title="Free Test Experience",
        start_date=dt.date(2024, 1, 10),
        end_date=dt.date(2024, 2, 20),
        experience_type=ExperienceType.OTHER,
        format_type=ExperienceFormatType.FREE,
        content="Test content in free format",
        category=ExperienceCategory.TECHNICAL_PROFICIENCY,
        tags="전문성",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert exp.title == "Free Test Experience"
    assert exp.format_type == ExperienceFormatType.FREE
    assert exp.content == "Test content in free format"


def test_experience_create_star_schema():
    """Test ExperienceCreate schema validation for STAR format."""
    data = {
        "title": "Test",
        "start_date": dt.date(2024, 6, 1),
        "end_date": dt.date(2024, 6, 15),
        "experience_type": ExperienceType.FULL_TIME,
        "format_type": ExperienceFormatType.STAR,
        "situation": "Situation",
        "task": "Task",
        "action": "Action",
        "result": "Result",
        "category": ExperienceCategory.TECHNICAL_PROFICIENCY,
    }
    schema = ExperienceCreate(**data)
    assert schema.title == "Test"
    assert schema.experience_type == ExperienceType.FULL_TIME
    assert schema.format_type == ExperienceFormatType.STAR


def test_experience_create_psi_schema():
    """Test ExperienceCreate schema validation for PSI format."""
    data = {
        "title": "PSI Test",
        "start_date": dt.date(2024, 3, 1),
        "end_date": dt.date(2024, 5, 30),
        "experience_type": ExperienceType.FULL_TIME,
        "format_type": ExperienceFormatType.PSI,
        "problem": "Problem",
        "solution": "Solution",
        "insight": "Insight",
        "category": ExperienceCategory.COLLABORATIVE_COMMUNICATION,
    }
    schema = ExperienceCreate(**data)
    assert schema.title == "PSI Test"
    assert schema.format_type == ExperienceFormatType.PSI
    assert schema.problem == "Problem"
    assert schema.solution == "Solution"
    assert schema.insight == "Insight"


def test_experience_create_free_schema():
    """Test ExperienceCreate schema validation for FREE format."""
    data = {
        "title": "Free Test",
        "start_date": dt.date(2024, 1, 10),
        "end_date": dt.date(2024, 2, 20),
        "experience_type": ExperienceType.OTHER,
        "format_type": ExperienceFormatType.FREE,
        "content": "Free format content",
        "category": ExperienceCategory.TECHNICAL_PROFICIENCY,
    }
    schema = ExperienceCreate(**data)
    assert schema.title == "Free Test"
    assert schema.format_type == ExperienceFormatType.FREE
    assert schema.content == "Free format content"


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


@patch("src.database.get_qdrant_client")
def test_create_psi_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    sample_psi_experience_data: dict,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test creating a PSI format experience successfully."""
    mock_get_qdrant.return_value = mock_qdrant_client

    response = client.post(
        "/api/v1/experiences",
        headers=auth_headers,
        json=sample_psi_experience_data,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_psi_experience_data["title"]
    assert data["problem"] == sample_psi_experience_data["problem"]
    assert data["solution"] == sample_psi_experience_data["solution"]
    assert data["insight"] == sample_psi_experience_data["insight"]
    assert data["format_type"] == "PSI"
    assert "tags" in data
    assert "id" in data
    assert "created_at" in data


@patch("src.database.get_qdrant_client")
def test_create_free_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    sample_free_experience_data: dict,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test creating a free format experience successfully."""
    mock_get_qdrant.return_value = mock_qdrant_client

    response = client.post(
        "/api/v1/experiences",
        headers=auth_headers,
        json=sample_free_experience_data,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_free_experience_data["title"]
    assert data["content"] == sample_free_experience_data["content"]
    assert data["format_type"] == "FREE"
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
        "format_type": "STAR",
        "situation": "Test situation",
        "task": "Test task",
        "action": "Test action",
        "result": "Test result",
        "category": "기술적 전문성",
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
        "format_type": "STAR",
        "situation": "Test situation",
        "task": "Test task",
        "action": "Test action",
        "result": "Test result",
        "category": "기술적 전문성",
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
        "format_type": "STAR",
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
def test_update_star_with_invalid_psi_fields(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test that updating a STAR experience with PSI fields fails."""
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
        "format_type": "STAR",
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

    # Try to update STAR experience with PSI fields
    update_data = {"problem": "This is a problem field"}

    response = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 400
    assert "STAR format does not support" in response.json()["detail"]
    assert "problem" in response.json()["detail"]


@patch("src.database.get_qdrant_client")
def test_update_psi_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test updating a PSI format experience."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "Original PSI Title",
        "start_date": "2024-03-01",
        "end_date": "2024-05-30",
        "experience_type": "정규직",
        "format_type": "PSI",
        "problem": "Original problem",
        "solution": "Original solution",
        "insight": "Original insight",
        "category": "협력적 소통",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    update_data = {"title": "Updated PSI Title", "insight": "Updated insight with more details"}

    response = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated PSI Title"
    assert data["insight"] == "Updated insight with more details"
    assert data["format_type"] == "PSI"


@patch("src.database.get_qdrant_client")
def test_update_psi_with_invalid_star_fields(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test that updating a PSI experience with STAR fields fails."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "Original PSI Title",
        "start_date": "2024-03-01",
        "end_date": "2024-05-30",
        "experience_type": "정규직",
        "format_type": "PSI",
        "problem": "Original problem",
        "solution": "Original solution",
        "insight": "Original insight",
        "category": "협력적 소통",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    # Try to update PSI experience with STAR fields
    update_data = {"situation": "This is a situation field", "task": "This is a task field"}

    response = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 400
    assert "PSI format does not support" in response.json()["detail"]
    assert "situation" in response.json()["detail"]


@patch("src.database.get_qdrant_client")
def test_update_free_experience_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test updating a free format experience."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "Original Free Title",
        "start_date": "2024-01-10",
        "end_date": "2024-02-20",
        "experience_type": "개인 활동",
        "format_type": "FREE",
        "content": "Original content",
        "category": "기술적 전문성",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    update_data = {"content": "Updated content with more information about the experience"}

    response = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Updated content with more information about the experience"
    assert data["format_type"] == "FREE"


@patch("src.database.get_qdrant_client")
def test_update_free_with_invalid_star_psi_fields(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test that updating a FREE experience with STAR or PSI fields fails."""
    mock_get_qdrant.return_value = mock_qdrant_client

    experience_id = str(uuid4())
    mock_point = MagicMock()
    mock_point.payload = {
        "id": experience_id,
        "user_id": str(test_user.id),
        "title": "Original Free Title",
        "start_date": "2024-01-10",
        "end_date": "2024-02-20",
        "experience_type": "개인 활동",
        "format_type": "FREE",
        "content": "Original content",
        "category": "기술적 전문성",
        "tags": "전문성",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    # Try to update FREE experience with STAR fields
    update_data = {"action": "This is an action field"}

    response = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 400
    assert "FREE format does not support" in response.json()["detail"]
    assert "action" in response.json()["detail"]


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
        "format_type": "STAR",
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
        "format_type": "STAR",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "AI/LLM, 문제해결",
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
        "format_type": "STAR",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "리서치",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_qdrant_client.retrieve.return_value = [mock_point]

    response = client.get(
        f"/api/v1/experiences/{experience_id}", headers=auth_headers
    )

    assert response.status_code == 404

@pytest.fixture
def test_project(session: Session, test_user: User) -> Project:
    """Create a test project."""
    project = Project(
        user_id=test_user.id,
        company="카카오",
        job_position="백엔드 개발자",
        recruit_notice="2024년 상반기 신입 개발자 공개채용",
        due_date=dt.date(2024, 12, 31),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@pytest.fixture
def test_question(session: Session, test_user: User, test_project: Project) -> Question:
    """Create a test question."""
    question = Question(
        project_id=test_project.id,
        user_id=test_user.id,
        question="본인이 가장 열정적으로 참여한 프로젝트 경험을 설명해 주세요.",
        max_length=1000,
        order=1,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


# Question Matching Tests
@patch("src.database.get_qdrant_client")
def test_get_experiences_by_question_success(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    test_question: Question,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test getting experiences matched with a question."""
    mock_get_qdrant.return_value = mock_qdrant_client

    # Mock Qdrant query response with similarity scores
    mock_point1 = MagicMock()
    mock_point1.payload = {
        "id": str(uuid4()),
        "user_id": str(test_user.id),
        "title": "AI 챗봇 개발",
        "start_date": "2024-06-01",
        "end_date": "2024-06-15",
        "experience_type": "동아리 활동",
        "format_type": "STAR",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "AI/LLM, 문제해결",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_point1.score = 0.92

    mock_point2 = MagicMock()
    mock_point2.payload = {
        "id": str(uuid4()),
        "user_id": str(test_user.id),
        "title": "웹 서비스 개발",
        "start_date": "2024-05-01",
        "end_date": "2024-05-31",
        "experience_type": "인턴",
        "format_type": "STAR",
        "situation": "Test",
        "task": "Test",
        "action": "Test",
        "result": "Test",
        "category": "기술적 전문성",
        "tags": "백엔드",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_point2.score = 0.75

    mock_qdrant_client.query_points.return_value = MagicMock(
        points=[mock_point1, mock_point2]
    )

    response = client.get(
        f"/api/v1/experiences/match-question/{test_question.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "experiences" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["experiences"]) == 2

    # Check first experience has higher score
    assert data["experiences"][0]["similarity_score"] == 0.92
    assert data["experiences"][1]["similarity_score"] == 0.75

    # Verify Qdrant query was called with correct parameters
    mock_qdrant_client.query_points.assert_called_once()


def test_get_experiences_by_question_unauthenticated(
    client: TestClient, test_question: Question
):
    """Test getting experiences by question without authentication."""
    response = client.get(
        f"/api/v1/experiences/match-question/{test_question.id}"
    )
    assert response.status_code == 401


@patch("src.database.get_qdrant_client")
def test_get_experiences_by_question_not_found(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test getting experiences with non-existent question."""
    mock_get_qdrant.return_value = mock_qdrant_client

    non_existent_question_id = uuid4()
    response = client.get(
        f"/api/v1/experiences/match-question/{non_existent_question_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "Question not found" in response.json()["detail"]


@patch("src.database.get_qdrant_client")
def test_get_experiences_by_question_other_user(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    session: Session,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test accessing another user's question."""
    mock_get_qdrant.return_value = mock_qdrant_client

    # Create another user and their project/question
    other_user = User(
        email="other@example.com",
        full_name="Other User",
        oauth_provider=OAuthProvider.GOOGLE,
        oauth_provider_id="google_other_123",
        is_active=True,
    )
    session.add(other_user)
    session.commit()
    session.refresh(other_user)

    other_project = Project(
        user_id=other_user.id,
        company="네이버",
        job_position="프론트엔드 개발자",
        recruit_notice="Test recruit notice",
    )
    session.add(other_project)
    session.commit()
    session.refresh(other_project)

    other_question = Question(
        project_id=other_project.id,
        user_id=other_user.id,
        question="Test question",
        order=1,
    )
    session.add(other_question)
    session.commit()
    session.refresh(other_question)

    response = client.get(
        f"/api/v1/experiences/match-question/{other_question.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "Question not found" in response.json()["detail"]


@patch("src.database.get_qdrant_client")
def test_get_experiences_by_question_empty_results(
    mock_get_qdrant,
    client: TestClient,
    auth_headers: dict,
    test_question: Question,
    mock_qdrant_client: MagicMock,
    mock_openai_client: MagicMock,
):
    """Test getting experiences when user has no experiences."""
    mock_get_qdrant.return_value = mock_qdrant_client

    # Mock empty Qdrant response
    mock_qdrant_client.query_points.return_value = MagicMock(points=[])

    response = client.get(
        f"/api/v1/experiences/match-question/{test_question.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["experiences"]) == 0
