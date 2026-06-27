"""add banners table

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-06-27 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "j5k6l7m8n9o0"
down_revision = "i4j5k6l7m8n9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "banners",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("image_url", sa.Text, nullable=False),
        sa.Column("link_url", sa.Text, nullable=True),
        sa.Column("is_visible", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("banners")
