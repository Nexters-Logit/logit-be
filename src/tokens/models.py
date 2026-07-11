"""토큰 시스템 DB 모델."""

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class TokenTransactionType(str, Enum):
    BALANCE_INIT = "balance_init"        # 토큰 계정 최초 생성 (잔액 0)
    MONTHLY_GRANT = "monthly_grant"      # 플랜별 월 토큰 지급
    SIGNUP_BONUS = "signup_bonus"        # 신규 가입 보너스 (50토큰, 1회)
    ATTENDANCE = "attendance"            # 출석 이벤트 (3토큰/일)
    REFERRAL_INVITER = "referral_inviter"  # 친구 초대 성공 — 초대한 쪽 (+10)
    REFERRAL_INVITEE = "referral_invitee"  # 친구 초대 성공 — 초대받은 쪽 (+10)
    CHAT_USAGE = "chat_usage"            # 채팅 사용 (-5)
    DRAFT_USAGE = "draft_usage"          # 초안 생성 사용 (-10)
    CHAT_REFUND = "chat_refund"          # 채팅/초안 실패 또는 비용 조정 환불 (+)
    ADMIN_GRANT = "admin_grant"          # 운영자 수동 지급
    ADMIN_RESET = "admin_reset"          # 운영자 수동 초기화


class UserToken(SQLModel, table=True):
    """유저별 토큰 잔액 및 월별 지급 상태."""

    __tablename__ = "user_tokens"

    user_id: UUID = Field(primary_key=True)
    balance: int = Field(default=0)
    last_monthly_grant_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    signup_bonus_granted: bool = Field(default=False)
    unnotified_referral_amount: int = Field(default=0)
    unnotified_referral_count: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TokenTransaction(SQLModel, table=True):
    """토큰 변동 이력."""

    __tablename__ = "token_transactions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=False)
    amount: int  # 양수=지급, 음수=차감
    # 마이그레이션이 이 컬럼을 순수 VARCHAR(30)으로 생성하므로, SQLModel의 기본
    # Enum→네이티브 postgres enum 매핑을 쓰면 스키마와 어긋나 INSERT가 실패한다.
    type: TokenTransactionType = Field(sa_column=Column(String(30), nullable=False))
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
    user_id: UUID
    date: date
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
