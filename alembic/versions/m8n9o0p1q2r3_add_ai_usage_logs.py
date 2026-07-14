"""add ai_usage_logs table

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-06-28 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "m8n9o0p1q2r3"
down_revision = "l7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("subscription_type", sa.String(20), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("endpoint", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_user_created", "ai_usage_logs", ["user_id", "created_at"])
    op.create_index("ix_ai_usage_subtype_created", "ai_usage_logs", ["subscription_type", "created_at"])
    op.create_index("ix_ai_usage_plan_created", "ai_usage_logs", ["plan", "created_at"])
    op.create_index("ix_ai_usage_subtype_endpoint_created", "ai_usage_logs", ["subscription_type", "endpoint", "created_at"])
    op.create_index("ix_ai_usage_created", "ai_usage_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_created", "ai_usage_logs")
    op.drop_index("ix_ai_usage_subtype_endpoint_created", "ai_usage_logs")
    op.drop_index("ix_ai_usage_plan_created", "ai_usage_logs")
    op.drop_index("ix_ai_usage_subtype_created", "ai_usage_logs")
    op.drop_index("ix_ai_usage_user_created", "ai_usage_logs")
    op.drop_table("ai_usage_logs")
