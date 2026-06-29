"""토큰 시스템 DB 모델."""

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class TokenTransactionType(str, Enum):
    MONTHLY_GRANT = "monthly_grant"      # 플랜별 월 토큰 지급
    SIGNUP_BONUS = "signup_bonus"        # 신규 가입 보너스 (50토큰, 1회)
    ATTENDANCE = "attendance"            # 출석 이벤트 (3토큰/일)
    REFERRAL_INVITER = "referral_inviter"  # 친구 초대 성공 — 초대한 쪽 (+10)
    REFERRAL_INVITEE = "referral_invitee"  # 친구 초대 성공 — 초대받은 쪽 (+10)
    CHAT_USAGE = "chat_usage"            # 채팅 사용 (-5)
    DRAFT_USAGE = "draft_usage"          # 초안 생성 사용 (-10)
    ADMIN_GRANT = "admin_grant"          # 운영자 수동 지급


class UserToken(SQLModel, table=True):
    """유저별 토큰 잔액 및 월별 지급 상태."""

    __tablename__ = "user_tokens"

    user_id: str = Field(primary_key=True, max_length=36)
    balance: int = Field(default=0)
    last_monthly_grant_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    signup_bonus_granted: bool = Field(default=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TokenTransaction(SQLModel, table=True):
    """토큰 변동 이력."""

    __tablename__ = "token_transactions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(max_length=36, index=False)
    amount: int  # 양수=지급, 음수=차감
    type: TokenTransactionType
    description: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AttendanceLog(SQLModel, table=True):
    """일별 출석 기록 (유저-날짜 유니크)."""

    __tablename__ = "attendance_logs"

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(max_length=36)
    date: date
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
