"""user_tokens: add unnotified signup bonus tracking

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-07-14 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "r3s4t5u6v7w8"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_tokens",
        sa.Column("unnotified_signup_bonus_amount", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_tokens", "unnotified_signup_bonus_amount")
