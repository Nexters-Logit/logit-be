"""Tests for users domain."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.security import create_access_token
from src.users.models import OAuthProvider, User


def test_read_users_me_authenticated(client: TestClient, session: Session) -> None:
    """Test reading current user with valid authentication."""
    # Create a test user
    user = User(
        email="test@example.com",
        full_name="Test User",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_123",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create access token
    access_token = create_access_token(subject=str(user.id))

    # Make authenticated request
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert data["oauth_provider"] == "google"
    assert data["is_active"] is True


def test_read_users_me_unauthenticated(client: TestClient) -> None:
    """Test reading current user without authentication."""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_read_users_me_invalid_token(client: TestClient) -> None:
    """Test reading current user with invalid token."""
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid_token_here"},
    )
    assert response.status_code == 401


def test_read_users_me_inactive_user(client: TestClient, session: Session) -> None:
    """Test reading current user when user is inactive."""
    # Create inactive user
    user = User(
        email="inactive@example.com",
        full_name="Inactive User",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_456",
        is_active=False,  # Inactive
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create access token
    access_token = create_access_token(subject=str(user.id))

    # Make authenticated request
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_update_user_me(client: TestClient, session: Session) -> None:
    """Test updating current user."""
    # Create a test user
    user = User(
        email="update@example.com",
        full_name="Original Name",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_789",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create access token
    access_token = create_access_token(subject=str(user.id))

    # Update user
    response = client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"full_name": "Updated Name"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["email"] == "update@example.com"  # Email unchanged


def test_delete_user_me(client: TestClient, session: Session) -> None:
    """Test deleting current user."""
    # Create a test user
    user = User(
        email="delete@example.com",
        full_name="To Be Deleted",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_999",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id

    # Create access token
    access_token = create_access_token(subject=str(user_id))

    # Delete user
    response = client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "User deleted successfully"

    # Verify user is deleted from database
    deleted_user = session.get(User, user_id)
    assert deleted_user is None
