"""add subscription_events table

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa

revision = "k6l7m8n9o0p1"
down_revision = "j5k6l7m8n9o0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sub_type", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("plan", sa.String(20), nullable=True),
        sa.Column("rebill_no", sa.String(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("payapp_response", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscription_events_user_id", "subscription_events", ["user_id"])
    op.create_index("ix_subscription_events_sub_type", "subscription_events", ["sub_type"])
    op.create_index("ix_subscription_events_created_at", "subscription_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_subscription_events_created_at", table_name="subscription_events")
    op.drop_index("ix_subscription_events_sub_type", table_name="subscription_events")
    op.drop_index("ix_subscription_events_user_id", table_name="subscription_events")
    op.drop_table("subscription_events")
