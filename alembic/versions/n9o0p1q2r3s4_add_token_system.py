"""add token system (user_tokens, token_transactions, attendance_logs, referral)

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-06-29 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "n9o0p1q2r3s4"
down_revision = "m8n9o0p1q2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users 테이블에 referral 컬럼 추가
    op.add_column("users", sa.Column("referral_code", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("referred_by_user_id", sa.String(36), nullable=True))
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    # 2. 유저별 토큰 잔액
    op.create_table(
        "user_tokens",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_monthly_grant_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signup_bonus_granted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. 토큰 트랜잭션 이력
    op.create_table(
        "token_transactions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_token_tx_user_created", "token_transactions", ["user_id", "created_at"])
    op.create_index("ix_token_tx_type", "token_transactions", ["type", "created_at"])

    # 4. 출석 로그 (유저-날짜 유니크)
    op.create_table(
        "attendance_logs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )
    op.create_index("ix_attendance_user", "attendance_logs", ["user_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_attendance_user", "attendance_logs")
    op.drop_table("attendance_logs")
    op.drop_index("ix_token_tx_type", "token_transactions")
    op.drop_index("ix_token_tx_user_created", "token_transactions")
    op.drop_table("token_transactions")
    op.drop_table("user_tokens")
    op.drop_index("ix_users_referral_code", "users")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
