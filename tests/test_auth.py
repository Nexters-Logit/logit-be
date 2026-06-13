"""Tests for auth domain."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.security import create_access_token, create_refresh_token
from src.users.models import OAuthProvider, User


def test_google_oauth_redirect(client: TestClient) -> None:
    """Test Google OAuth redirect endpoint."""
    response = client.get("/api/v1/auth/google", follow_redirects=False)

    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]
    assert "client_id=" in response.headers["location"]


def test_apple_oauth_redirect(client: TestClient) -> None:
    """Test Apple OAuth redirect endpoint."""
    response = client.get("/api/v1/auth/apple", follow_redirects=False)

    assert response.status_code == 307
    assert "appleid.apple.com" in response.headers["location"]


@patch("src.auth.router._verify_oauth_state", return_value=None)
@patch("src.auth.service.httpx.AsyncClient.post")
@patch("src.auth.service.httpx.AsyncClient.get")
async def test_google_callback_new_user(
    mock_get: AsyncMock,
    mock_post: AsyncMock,
    mock_verify_state: AsyncMock,
    client: TestClient,
    session: Session,
) -> None:
    """Test Google OAuth callback with new user (web flow: redirects to frontend with temp code)."""
    # Mock Google token exchange
    mock_post.return_value = AsyncMock(
        status_code=200,
        json=lambda: {"access_token": "google_access_token"},
    )

    # Mock Google userinfo (v2 API uses "id" not "sub")
    mock_get.return_value = AsyncMock(
        status_code=200,
        json=lambda: {
            "email": "newuser@gmail.com",
            "name": "New User",
            "id": "google_12345",
            "picture": "https://example.com/photo.jpg",
        },
    )

    # Web flow redirects to frontend with temp code (not following redirects)
    response = client.get(
        "/api/v1/auth/google/callback?code=test_auth_code&state=test_state",
        follow_redirects=False,
    )

    # Should redirect to frontend with a temp code (not an error)
    assert response.status_code == 307
    location = response.headers["location"]
    assert "error" not in location
    assert "code=" in location

    # Verify user was created in DB
    session.expire_all()
    user = session.query(User).filter(User.email == "newuser@gmail.com").first()
    assert user is not None
    assert user.full_name == "New User"
    assert user.oauth_provider == OAuthProvider.google
    assert user.profile_image_url == "https://example.com/photo.jpg"


@patch("src.auth.router._verify_oauth_state", return_value=None)
@patch("src.auth.service.httpx.AsyncClient.post")
@patch("src.auth.service.httpx.AsyncClient.get")
async def test_google_callback_existing_user(
    mock_get: AsyncMock,
    mock_post: AsyncMock,
    mock_verify_state: AsyncMock,
    client: TestClient,
    session: Session,
) -> None:
    """Test Google OAuth callback with existing user (web flow: redirects to frontend)."""
    # Create existing user
    existing_user = User(
        email="existing@gmail.com",
        full_name="Existing User",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_67890",
        is_active=True,
    )
    session.add(existing_user)
    session.commit()

    # Mock Google token exchange
    mock_post.return_value = AsyncMock(
        status_code=200,
        json=lambda: {"access_token": "google_access_token"},
    )

    # Mock Google userinfo (v2 API uses "id" not "sub")
    mock_get.return_value = AsyncMock(
        status_code=200,
        json=lambda: {
            "email": "existing@gmail.com",
            "name": "Updated Name",
            "id": "google_67890",
            "picture": "https://example.com/new_photo.jpg",
        },
    )

    # Web flow redirects to frontend with temp code
    response = client.get(
        "/api/v1/auth/google/callback?code=test_auth_code&state=test_state",
        follow_redirects=False,
    )

    assert response.status_code == 307
    location = response.headers["location"]
    assert "error" not in location
    assert "code=" in location


def test_refresh_token_success(client: TestClient, session: Session) -> None:
    """Test token refresh with valid refresh token."""
    # Create a test user
    user = User(
        email="refresh@example.com",
        full_name="Refresh User",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_refresh",
        is_active=True,
    )

    # Create refresh token
    refresh_token = create_refresh_token(subject=str(user.id))
    user.refresh_token = refresh_token

    session.add(user)
    session.commit()

    # Request new tokens
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_token_invalid(client: TestClient) -> None:
    """Test token refresh with invalid refresh token."""
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_refresh_token"},
    )

    assert response.status_code == 401


def test_logout_success(client: TestClient, session: Session) -> None:
    """Test logout with valid refresh token."""
    # Create a test user with refresh token
    user = User(
        email="logout@example.com",
        full_name="Logout User",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id="google_logout",
        is_active=True,
    )

    refresh_token = create_refresh_token(subject=str(user.id))
    user.refresh_token = refresh_token

    session.add(user)
    session.commit()
    session.refresh(user)

    # Logout
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 204


def test_logout_invalid_token(client: TestClient) -> None:
    """Test logout with invalid refresh token returns 204 (lenient logout)."""
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "invalid_token"},
    )

    assert response.status_code == 204
