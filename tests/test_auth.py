"""Tests for auth domain."""

from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.security import create_access_token, create_refresh_token
from src.tokens.models import AttendanceLog, TokenTransaction, TokenTransactionType
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


def test_apple_callback_error_redirect_uses_303(client: TestClient) -> None:
    """
    Apple은 response_mode=form_post라 콜백을 POST로 호출한다. 프론트로
    되돌려보내는 리디렉션이 307(원래 메서드 유지)이면 브라우저가 GET만
    받는 프론트 /auth/callback 페이지에 POST로 재요청해 405가 발생한다.
    303 See Other를 써서 브라우저가 항상 GET으로 전환하도록 해야 한다.
    """
    # state가 유효하지 않으므로 Apple API를 호출하지 않고 바로 에러 리디렉션됨
    response = client.post(
        "/api/v1/auth/apple/callback",
        data={"code": "irrelevant", "state": "invalid_or_expired_state"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "error=oauth_failed" in response.headers["location"]


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

    # Should redirect to frontend with a temp code (not an error).
    # 303 See Other — POST로 호출되는 Apple 콜백에서도 브라우저가 리디렉션 시
    # GET으로 전환하도록 한다 (307은 원래 메서드를 유지해 Apple form_post
    # 콜백에서 프론트 페이지가 405를 반환하는 문제가 있었음).
    assert response.status_code == 303
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

    assert response.status_code == 303
    location = response.headers["location"]
    assert "error" not in location
    assert "code=" in location


def _exchange_temp_code(client: TestClient, redirect_location: str) -> dict:
    """콜백 리디렉션 URL에서 임시 코드를 추출해 /auth/token으로 교환한다."""
    temp_code = parse_qs(urlparse(redirect_location).query)["code"][0]
    resp = client.post(
        "/api/v1/auth/token",
        json={"code": temp_code, "platform": "web"},
    )
    assert resp.status_code == 200
    return resp.json()


@patch("src.auth.router._verify_oauth_state", return_value=None)
@patch("src.auth.service.httpx.AsyncClient.post")
@patch("src.auth.service.httpx.AsyncClient.get")
def test_new_user_login_grants_signup_bonus_and_attendance_via_balance(
    mock_get: AsyncMock,
    mock_post: AsyncMock,
    mock_verify_state: AsyncMock,
    client: TestClient,
    session: Session,
) -> None:
    """
    회원가입 보너스는 계정 생성 시점(로그인 플로우)에 지급되지만,
    실제 값 확인은 인증과 분리된 GET /tokens/balance에서 이뤄진다.
    출석도 동일 엔드포인트에서 그 날 첫 조회 시 지급된다.
    """
    mock_post.return_value = AsyncMock(
        status_code=200,
        json=lambda: {"access_token": "google_access_token"},
    )
    mock_get.return_value = AsyncMock(
        status_code=200,
        json=lambda: {
            "email": "attendance@gmail.com",
            "name": "Attendance User",
            "id": "google_attendance",
            "picture": None,
        },
    )

    response = client.get(
        "/api/v1/auth/google/callback?code=test_auth_code&state=test_state",
        follow_redirects=False,
    )
    login_data = _exchange_temp_code(client, response.headers["location"])
    # 로그인 응답 자체에는 토큰 지급 내역이 더 이상 포함되지 않는다
    assert "signup_bonus_amount" not in login_data
    assert "attendance_amount" not in login_data

    session.expire_all()
    user = session.query(User).filter(User.email == "attendance@gmail.com").first()
    assert user is not None

    # 계정 생성 시점에 가입 보너스 트랜잭션은 이미 기록되어 있다
    bonus_tx = (
        session.query(TokenTransaction)
        .filter(
            TokenTransaction.user_id == user.id,
            TokenTransaction.type == TokenTransactionType.SIGNUP_BONUS,
        )
        .first()
    )
    assert bonus_tx is not None
    assert bonus_tx.amount == 50

    balance_resp = client.get(
        "/api/v1/tokens/balance",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    balance = balance_resp.json()
    assert balance["signup_bonus_received"] is True
    assert balance["signup_bonus_amount"] == 50
    assert balance["attendance_received"] is True
    assert balance["attendance_amount"] == 3

    attendance_log = (
        session.query(AttendanceLog).filter(AttendanceLog.user_id == user.id).first()
    )
    assert attendance_log is not None

    # 같은 날 두 번째 조회에서는 둘 다 중복 지급/재알림되지 않아야 한다
    second_balance = client.get(
        "/api/v1/tokens/balance",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    ).json()
    assert second_balance["signup_bonus_received"] is False
    assert second_balance["signup_bonus_amount"] == 0
    assert second_balance["attendance_received"] is False
    assert second_balance["attendance_amount"] == 0


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
