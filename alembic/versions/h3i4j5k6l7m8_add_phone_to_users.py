"""add phone to users

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-06-13 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "h3i4j5k6l7m8"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
