"""add card info and subscription period to payment_records

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-13 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "g2h3i4j5k6l7"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_records", sa.Column("card_name", sa.String(), nullable=True))
    op.add_column("payment_records", sa.Column("card_number", sa.String(), nullable=True))
    op.add_column("payment_records", sa.Column("receipt_url", sa.String(), nullable=True))
    op.add_column("payment_records", sa.Column("subscription_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_records", sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_records", "subscription_expires_at")
    op.drop_column("payment_records", "subscription_started_at")
    op.drop_column("payment_records", "receipt_url")
    op.drop_column("payment_records", "card_number")
    op.drop_column("payment_records", "card_name")
