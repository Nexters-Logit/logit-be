"""add show_on_mobile to plans

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-06-28 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "l7m8n9o0p1q2"
down_revision = "k6l7m8n9o0p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("show_on_mobile", sa.Boolean(), nullable=False, server_default="true"),
    )
    # MCP 구독은 기본적으로 모바일 미노출
    op.execute("UPDATE plans SET show_on_mobile = false WHERE subscription_type = 'mcp'")


def downgrade() -> None:
    op.drop_column("plans", "show_on_mobile")
