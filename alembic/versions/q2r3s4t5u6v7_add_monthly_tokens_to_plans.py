"""add monthly_tokens to plans

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-07-12 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("monthly_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    # 기존 시딩된 플랜에 현재 토큰 지급량(tokens/constants.PLAN_MONTHLY_TOKENS)을 반영
    op.execute("UPDATE plans SET monthly_tokens = 400 WHERE id = 'logit:lite'")
    op.execute("UPDATE plans SET monthly_tokens = 2000 WHERE id = 'logit:pro'")


def downgrade() -> None:
    op.drop_column("plans", "monthly_tokens")
