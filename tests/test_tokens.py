"""토큰 시스템 테스트."""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
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
    # 첫 조회 시 월 토큰 + 당일 출석 토큰 + (가입 시점에 못 받았던) 가입 보너스가
    # 안전망(grant_signup_bonus 멱등 재시도)을 통해 함께 자동 지급된다.
    # make_user()는 OAuth 가입 플로우를 거치지 않으므로 signup_bonus_granted가
    # False인 상태 — 이 조회에서 안전망이 지급해준다.
    assert data["monthly_grant_received"] is True
    assert data["attendance_received"] is True
    assert data["signup_bonus_received"] is True
    assert data["signup_bonus_amount"] == SIGNUP_BONUS_TOKENS
    assert data["balance"] == (
        PLAN_MONTHLY_TOKENS["free"] + data["attendance_amount"] + SIGNUP_BONUS_TOKENS
    )

    # 두 번째 조회에서는 안전망도 재지급하지 않는다 (멱등)
    second = client.get("/api/v1/tokens/balance", headers=auth_header(token)).json()
    assert second["signup_bonus_received"] is False
    assert second["signup_bonus_amount"] == 0
    assert second["balance"] == data["balance"]


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


async def test_apply_referral_concurrent_requests_only_credit_once(
    session: Session, async_session: AsyncSession,
) -> None:
    """
    동시 요청(더블 탭/네트워크 재시도)으로 두 요청이 모두
    invitee.referred_by_user_id=None인 상태를 읽더라도, 원자적
    UPDATE...WHERE claim 덕분에 한쪽만 성공하고 토큰도 1회만 지급돼야 한다.
    두 개의 독립된 AsyncSession으로 "동시에 들어온 두 요청"을 시뮬레이션한다.
    """
    from src.users.referral import apply_referral_code, get_or_create_referral_code
    from tests.conftest import _async_engine

    inviter, _ = make_user(session, "race_inviter@example.com")
    invitee, _ = make_user(session, "race_invitee@example.com")

    inviter_async = await async_session.get(User, inviter.id)
    code = await get_or_create_referral_code(async_session, inviter_async)
    await async_session.commit()

    async with AsyncSession(_async_engine) as session_a, AsyncSession(_async_engine) as session_b:
        invitee_a = await session_a.get(User, invitee.id)
        invitee_b = await session_b.get(User, invitee.id)
        # 두 세션 모두 아직 초대받지 않은 상태를 읽었다 (레이스 재현)
        assert invitee_a.referred_by_user_id is None
        assert invitee_b.referred_by_user_id is None

        result_a = await apply_referral_code(session_a, invitee_a, code)
        await session_a.commit()

        result_b = await apply_referral_code(session_b, invitee_b, code)
        await session_b.commit()

    assert result_a["success"] is True
    assert result_b == {"success": False, "reason": "already_referred"}

    inviter_balance = await async_session.get(UserToken, inviter.id)
    await async_session.refresh(inviter_balance)
    assert inviter_balance.balance == REFERRAL_TOKENS


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
