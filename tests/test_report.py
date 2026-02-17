"""Tests for report domain."""

import datetime as dt
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client.models import PointStruct
from sqlmodel import Session

from src.experience.models import Experience, ExperienceCategory, ExperienceFormatType, ExperienceType
from src.report import service
from src.security import create_access_token
from src.users.models import OAuthProvider, User


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing."""
    return MagicMock()


@pytest.fixture
def test_user(session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        oauth_provider=OAuthProvider.google,
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
def sample_experiences(test_user: User) -> list[Experience]:
    """Create sample experiences for testing."""
    return [
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="AI 챗봇 개발",
            start_date=dt.date(2024, 6, 1),
            end_date=dt.date(2024, 6, 15),
            experience_type=ExperienceType.GROUP_ACTIVITY,
            format_type=ExperienceFormatType.STAR,
            situation="Test situation",
            task="Test task",
            action="Test action",
            result="Test result",
            category=ExperienceCategory.TECHNICAL_PROFICIENCY,
            tags="AI/LLM, API연동, 백엔드",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="팀 협업 프로세스 개선",
            start_date=dt.date(2024, 3, 1),
            end_date=dt.date(2024, 5, 30),
            experience_type=ExperienceType.FULL_TIME,
            format_type=ExperienceFormatType.PSI,
            problem="Test problem",
            solution="Test solution",
            insight="Test insight",
            category=ExperienceCategory.COLLABORATIVE_COMMUNICATION,
            tags="커뮤니케이션, 프로세스개선",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="오픈소스 기여",
            start_date=dt.date(2024, 1, 10),
            end_date=dt.date(2024, 2, 20),
            experience_type=ExperienceType.OTHER,
            format_type=ExperienceFormatType.FREE,
            content="Test content",
            category=ExperienceCategory.TECHNICAL_PROFICIENCY,
            tags="프론트엔드, 코드리뷰",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="인턴 경험",
            start_date=dt.date(2024, 7, 1),
            end_date=dt.date(2024, 8, 31),
            experience_type=ExperienceType.INTERN,
            format_type=ExperienceFormatType.STAR,
            situation="Intern situation",
            task="Intern task",
            action="Intern action",
            result="Intern result",
            category=ExperienceCategory.LEADERSHIP_INITIATIVE,
            tags="백엔드, API연동",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="봉사활동",
            start_date=dt.date(2024, 9, 1),
            end_date=dt.date(2024, 9, 30),
            experience_type=ExperienceType.VOLUNTEER,
            format_type=ExperienceFormatType.FREE,
            content="Volunteer content",
            category=ExperienceCategory.COLLABORATIVE_COMMUNICATION,
            tags="커뮤니케이션, 문제해결",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]


# Service Tests
def test_get_experience_type_counts(mock_qdrant_client, test_user: User, sample_experiences):
    """Test getting experience type counts."""
    # Mock scroll result
    mock_points = [
        MagicMock(payload=exp.model_dump())
        for exp in sample_experiences
    ]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    # Call service function
    type_counts, total = service.get_experience_type_counts(
        client=mock_qdrant_client,
        user_id=str(test_user.id),
    )

    # Assertions
    assert total == 5
    assert type_counts[ExperienceType.GROUP_ACTIVITY.value] == 1
    assert type_counts[ExperienceType.FULL_TIME.value] == 1
    assert type_counts[ExperienceType.OTHER.value] == 1
    assert type_counts[ExperienceType.INTERN.value] == 1
    assert type_counts[ExperienceType.VOLUNTEER.value] == 1


def test_get_experience_category_counts(mock_qdrant_client, test_user: User, sample_experiences):
    """Test getting experience category counts."""
    # Mock scroll result
    mock_points = [
        MagicMock(payload=exp.model_dump())
        for exp in sample_experiences
    ]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    # Call service function
    category_counts, total = service.get_experience_category_counts(
        client=mock_qdrant_client,
        user_id=str(test_user.id),
    )

    # Assertions
    assert total == 5
    assert category_counts[ExperienceCategory.TECHNICAL_PROFICIENCY.value] == 2
    assert category_counts[ExperienceCategory.COLLABORATIVE_COMMUNICATION.value] == 2
    assert category_counts[ExperienceCategory.LEADERSHIP_INITIATIVE.value] == 1


def test_get_experience_tag_counts(mock_qdrant_client, test_user: User, sample_experiences):
    """Test getting experience tag counts."""
    # Mock scroll result
    mock_points = [
        MagicMock(payload=exp.model_dump())
        for exp in sample_experiences
    ]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    # Call service function
    tag_counts, total = service.get_experience_tag_counts(
        client=mock_qdrant_client,
        user_id=str(test_user.id),
    )

    # Assertions
    assert total == 5
    # API연동 appears in 2 experiences
    assert tag_counts["API연동"] == 2
    # 백엔드 appears in 2 experiences
    assert tag_counts["백엔드"] == 2
    # 커뮤니케이션 appears in 2 experiences
    assert tag_counts["커뮤니케이션"] == 2
    # AI/LLM appears in 1 experience
    assert tag_counts["AI/LLM"] == 1
    # 프로세스개선 appears in 1 experience
    assert tag_counts["프로세스개선"] == 1
    # 프론트엔드 appears in 1 experience
    assert tag_counts["프론트엔드"] == 1
    # 코드리뷰 appears in 1 experience
    assert tag_counts["코드리뷰"] == 1
    # 문제해결 appears in 1 experience
    assert tag_counts["문제해결"] == 1


def test_get_experience_tag_counts_with_empty_tags(mock_qdrant_client, test_user: User):
    """Test getting tag counts when some experiences have empty tags."""
    experiences = [
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="Test 1",
            start_date=dt.date(2024, 1, 1),
            experience_type=ExperienceType.FULL_TIME,
            format_type=ExperienceFormatType.STAR,
            situation="Test",
            task="Test",
            action="Test",
            result="Test",
            category=ExperienceCategory.TECHNICAL_PROFICIENCY,
            tags="태그1, 태그2",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Experience(
            id=str(uuid4()),
            user_id=str(test_user.id),
            title="Test 2",
            start_date=dt.date(2024, 2, 1),
            experience_type=ExperienceType.INTERN,
            format_type=ExperienceFormatType.FREE,
            content="Test",
            category=ExperienceCategory.TECHNICAL_PROFICIENCY,
            tags="",  # Empty tags
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]

    mock_points = [MagicMock(payload=exp.model_dump()) for exp in experiences]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    tag_counts, total = service.get_experience_tag_counts(
        client=mock_qdrant_client,
        user_id=str(test_user.id),
    )

    assert total == 2
    assert tag_counts["태그1"] == 1
    assert tag_counts["태그2"] == 1


# Router/API Tests
def test_get_experience_type_count_api(client: TestClient, auth_headers: dict, mock_qdrant_client, test_user: User, sample_experiences):
    """Test GET /api/v1/report/experience-type-count endpoint."""
    from src.main import app
    from src.users.dependencies import get_current_user
    from src.database import get_qdrant_client

    # Mock Qdrant dependency
    mock_points = [MagicMock(payload=exp.model_dump()) for exp in sample_experiences]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    # Override dependencies
    async def override_get_current_user():
        return test_user

    def override_get_qdrant_client():
        return mock_qdrant_client

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_qdrant_client] = override_get_qdrant_client

    try:
        # Make request
        response = client.get("/api/v1/report/experience-type-count", headers=auth_headers)
    finally:
        # Cleanup
        app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert data["total"] == 5
    assert len(data["data"]) == 5

    # Check that all types are present
    types_in_response = {item["type"] for item in data["data"]}
    assert ExperienceType.GROUP_ACTIVITY.value in types_in_response
    assert ExperienceType.FULL_TIME.value in types_in_response
    assert ExperienceType.INTERN.value in types_in_response


def test_get_experience_category_count_api(client: TestClient, auth_headers: dict, mock_qdrant_client, test_user: User, sample_experiences):
    """Test GET /api/v1/report/experience-category-count endpoint."""
    from src.main import app
    from src.users.dependencies import get_current_user
    from src.database import get_qdrant_client

    # Mock Qdrant dependency
    mock_points = [MagicMock(payload=exp.model_dump()) for exp in sample_experiences]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    # Override dependencies
    async def override_get_current_user():
        return test_user

    def override_get_qdrant_client():
        return mock_qdrant_client

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_qdrant_client] = override_get_qdrant_client

    try:
        # Make request
        response = client.get("/api/v1/report/experience-category-count", headers=auth_headers)
    finally:
        # Cleanup
        app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert data["total"] == 5
    assert len(data["data"]) == 3  # 3 unique categories

    # Check that categories are present
    categories_in_response = {item["category"] for item in data["data"]}
    assert ExperienceCategory.TECHNICAL_PROFICIENCY.value in categories_in_response
    assert ExperienceCategory.COLLABORATIVE_COMMUNICATION.value in categories_in_response


def test_get_experience_tag_count_api(client: TestClient, auth_headers: dict, mock_qdrant_client, test_user: User, sample_experiences):
    """Test GET /api/v1/report/experience-tag-count endpoint."""
    from src.main import app
    from src.users.dependencies import get_current_user
    from src.database import get_qdrant_client

    # Mock Qdrant dependency
    mock_points = [MagicMock(payload=exp.model_dump()) for exp in sample_experiences]
    mock_qdrant_client.scroll.return_value = (mock_points, None)

    # Override dependencies
    async def override_get_current_user():
        return test_user

    def override_get_qdrant_client():
        return mock_qdrant_client

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_qdrant_client] = override_get_qdrant_client

    try:
        # Make request
        response = client.get("/api/v1/report/experience-tag-count", headers=auth_headers)
    finally:
        # Cleanup
        app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert data["total"] == 5

    # Tags should be sorted by count (descending)
    if len(data["data"]) > 1:
        for i in range(len(data["data"]) - 1):
            assert data["data"][i]["count"] >= data["data"][i + 1]["count"]

    # Check that some expected tags are present
    tags_in_response = {item["tag"] for item in data["data"]}
    assert "API연동" in tags_in_response
    assert "백엔드" in tags_in_response
    assert "커뮤니케이션" in tags_in_response


def test_report_apis_require_authentication(client: TestClient):
    """Test that all report endpoints require authentication."""
    endpoints = [
        "/api/v1/report/experience-type-count",
        "/api/v1/report/experience-category-count",
        "/api/v1/report/experience-tag-count",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401  # Unauthorized


def test_get_experience_type_count_with_no_experiences(client: TestClient, auth_headers: dict, mock_qdrant_client, test_user: User):
    """Test type count endpoint when user has no experiences."""
    from src.main import app
    from src.users.dependencies import get_current_user
    from src.database import get_qdrant_client

    # Mock empty result
    mock_qdrant_client.scroll.return_value = ([], None)

    # Override dependencies
    async def override_get_current_user():
        return test_user

    def override_get_qdrant_client():
        return mock_qdrant_client

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_qdrant_client] = override_get_qdrant_client

    try:
        # Make request
        response = client.get("/api/v1/report/experience-type-count", headers=auth_headers)
    finally:
        # Cleanup
        app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["data"]) == 0
