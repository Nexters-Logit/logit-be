"""token tables user_id: String(36) → UUID

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-07-01 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "o0p1q2r3s4t5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 인덱스는 컬럼 타입 변경 전에 제거해야 한다
    op.drop_index("ix_token_tx_user_created", table_name="token_transactions")
    op.drop_index("ix_attendance_user", table_name="attendance_logs")

    op.alter_column(
        "user_tokens", "user_id",
        type_=sa.UUID(),
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "token_transactions", "user_id",
        type_=sa.UUID(),
        nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "attendance_logs", "user_id",
        type_=sa.UUID(),
        nullable=False,
        postgresql_using="user_id::uuid",
    )

    op.create_index("ix_token_tx_user_created", "token_transactions", ["user_id", "created_at"])
    op.create_index("ix_attendance_user", "attendance_logs", ["user_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_token_tx_user_created", table_name="token_transactions")
    op.drop_index("ix_attendance_user", table_name="attendance_logs")

    op.alter_column(
        "user_tokens", "user_id",
        type_=sa.String(36),
        postgresql_using="user_id::varchar",
    )
    op.alter_column(
        "token_transactions", "user_id",
        type_=sa.String(36),
        nullable=False,
        postgresql_using="user_id::varchar",
    )
    op.alter_column(
        "attendance_logs", "user_id",
        type_=sa.String(36),
        nullable=False,
        postgresql_using="user_id::varchar",
    )

    op.create_index("ix_token_tx_user_created", "token_transactions", ["user_id", "created_at"])
    op.create_index("ix_attendance_user", "attendance_logs", ["user_id", "date"])
