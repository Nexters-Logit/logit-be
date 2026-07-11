"""user_tokens: add unnotified referral reward tracking

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-07-11 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "p1q2r3s4t5u6"
down_revision = "o0p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_tokens",
        sa.Column("unnotified_referral_amount", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_tokens",
        sa.Column("unnotified_referral_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_tokens", "unnotified_referral_count")
    op.drop_column("user_tokens", "unnotified_referral_amount")
