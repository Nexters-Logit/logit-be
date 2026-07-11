"""토큰 시스템 테스트."""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.security import create_access_token
from src.tokens.constants import (
    CHAT_TOKEN_COST,
    DRAFT_TOKEN_COST,
    PLAN_MONTHLY_TOKENS,
    REFERRAL_TOKENS,
    SIGNUP_BONUS_TOKENS,
)
from src.tokens.models import AttendanceLog, TokenTransaction, TokenTransactionType, UserToken
from src.users.models import OAuthProvider, User


# ── 헬퍼 ─────────────────────────────────────────────────────────

def make_user(session: Session, email: str = "test@example.com") -> tuple[User, str]:
    user = User(
        email=email,
        full_name="Test User",
        oauth_provider=OAuthProvider.google,
        oauth_provider_id=str(uuid4()),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(subject=str(user.id))
    return user, token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── 토큰 잔액 조회 ────────────────────────────────────────────────

def test_get_balance_no_record(client: TestClient, session: Session) -> None:
    """레코드 없는 유저도 0 잔액을 반환해야 한다."""
    _, token = make_user(session)
    resp = client.get("/api/v1/tokens/balance", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "free"
    assert data["monthly_tokens"] == PLAN_MONTHLY_TOKENS["free"]
    # 첫 조회 시 월 토큰이 자동 지급된다
    assert data["balance"] == PLAN_MONTHLY_TOKENS["free"]


def test_get_balance_monthly_grant_not_doubled(client: TestClient, session: Session) -> None:
    """동일 결제 주기에 두 번 조회해도 월 토큰이 중복 지급되지 않는다."""
    _, token = make_user(session)
    resp1 = client.get("/api/v1/tokens/balance", headers=auth_header(token))
    resp2 = client.get("/api/v1/tokens/balance", headers=auth_header(token))
    assert resp1.json()["balance"] == resp2.json()["balance"]


# ── 친구 초대 ────────────────────────────────────────────────────

def test_get_referral_code(client: TestClient, session: Session) -> None:
    """초대 코드 조회 시 LOGIT- 으로 시작하는 코드를 반환해야 한다."""
    _, token = make_user(session)
    resp = client.get("/api/v1/users/referral", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"].startswith("LOGIT-")
    assert data["invited_count"] == 0


def test_referral_code_stable(client: TestClient, session: Session) -> None:
    """같은 유저의 초대 코드는 항상 동일해야 한다."""
    _, token = make_user(session)
    r1 = client.get("/api/v1/users/referral", headers=auth_header(token)).json()["code"]
    r2 = client.get("/api/v1/users/referral", headers=auth_header(token)).json()["code"]
    assert r1 == r2


def test_apply_referral_code_success(client: TestClient, session: Session) -> None:
    """유효한 초대 코드 입력 시 양쪽 각 +10 토큰."""
    _, inviter_token = make_user(session, "inviter@example.com")
    invitee_user, invitee_token = make_user(session, "invitee@example.com")

    # inviter 코드 조회
    code = client.get("/api/v1/users/referral", headers=auth_header(inviter_token)).json()["code"]

    # invitee가 코드 입력
    resp = client.post(
        "/api/v1/users/referral/apply",
        headers=auth_header(invitee_token),
        json={"code": code},
    )
    assert resp.status_code == 200

    # 양쪽 잔액에 +10 반영 확인 (월 토큰 초기화 후 체크)
    inv_balance = client.get("/api/v1/tokens/balance", headers=auth_header(inviter_token)).json()["balance"]
    invitee_balance = client.get("/api/v1/tokens/balance", headers=auth_header(invitee_token)).json()["balance"]

    # inviter: 월 토큰(50) + 초대 보상(10)
    assert inv_balance >= PLAN_MONTHLY_TOKENS["free"] + REFERRAL_TOKENS
    # invitee: 월 토큰(50) + 초대 보상(10)
    assert invitee_balance >= PLAN_MONTHLY_TOKENS["free"] + REFERRAL_TOKENS


def test_apply_referral_self_rejected(client: TestClient, session: Session) -> None:
    """자기 자신의 초대 코드는 사용 불가."""
    _, token = make_user(session)
    code = client.get("/api/v1/users/referral", headers=auth_header(token)).json()["code"]
    resp = client.post(
        "/api/v1/users/referral/apply",
        headers=auth_header(token),
        json={"code": code},
    )
    assert resp.status_code == 400


def test_apply_referral_duplicate_rejected(client: TestClient, session: Session) -> None:
    """이미 초대 코드를 사용한 유저는 다시 사용 불가."""
    _, inviter_token = make_user(session, "inv1@example.com")
    _, invitee_token = make_user(session, "inv2@example.com")

    code = client.get("/api/v1/users/referral", headers=auth_header(inviter_token)).json()["code"]
    client.post("/api/v1/users/referral/apply", headers=auth_header(invitee_token), json={"code": code})

    resp = client.post("/api/v1/users/referral/apply", headers=auth_header(invitee_token), json={"code": code})
    assert resp.status_code == 409


def test_apply_invalid_code(client: TestClient, session: Session) -> None:
    """잘못된 초대 코드는 404를 반환해야 한다."""
    _, token = make_user(session)
    resp = client.post(
        "/api/v1/users/referral/apply",
        headers=auth_header(token),
        json={"code": "LOGIT-INVALID"},
    )
    assert resp.status_code == 404


def test_referral_reward_notification_claimed_once(client: TestClient, session: Session) -> None:
    """초대자는 초대 성공 후 다음 잔액 조회에서 딱 1회만 보상 알림을 받는다."""
    _, inviter_token = make_user(session, "notif_inviter@example.com")
    _, invitee_token = make_user(session, "notif_invitee@example.com")

    code = client.get("/api/v1/users/referral", headers=auth_header(inviter_token)).json()["code"]
    client.post("/api/v1/users/referral/apply", headers=auth_header(invitee_token), json={"code": code})

    first = client.get("/api/v1/tokens/balance", headers=auth_header(inviter_token)).json()
    assert first["referral_reward_received"] is True
    assert first["referral_reward_amount"] == REFERRAL_TOKENS
    assert first["referral_reward_count"] == 1

    second = client.get("/api/v1/tokens/balance", headers=auth_header(inviter_token)).json()
    assert second["referral_reward_received"] is False
    assert second["referral_reward_amount"] == 0
    assert second["referral_reward_count"] == 0


# ── 초대 현황 ────────────────────────────────────────────────────

def test_referral_invited_count(client: TestClient, session: Session) -> None:
    """초대 성공 후 invited_count가 증가해야 한다."""
    _, inviter_token = make_user(session, "counter_inv@example.com")
    _, invitee_token = make_user(session, "counter_invitee@example.com")

    code = client.get("/api/v1/users/referral", headers=auth_header(inviter_token)).json()["code"]
    client.post("/api/v1/users/referral/apply", headers=auth_header(invitee_token), json={"code": code})

    stats = client.get("/api/v1/users/referral", headers=auth_header(inviter_token)).json()
    assert stats["invited_count"] == 1
