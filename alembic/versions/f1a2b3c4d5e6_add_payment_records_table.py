"""add payment_records table

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2025-01-01 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_type", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("mul_no", sa.String(), nullable=True),
        sa.Column("rebill_no", sa.String(), nullable=True),
        sa.Column("pay_state", sa.Integer(), nullable=True),
        sa.Column("raw_webhook_data", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_records_user_id", "payment_records", ["user_id"])
    op.create_index("ix_payment_records_mul_no", "payment_records", ["mul_no"])


def downgrade() -> None:
    op.drop_index("ix_payment_records_mul_no", table_name="payment_records")
    op.drop_index("ix_payment_records_user_id", table_name="payment_records")
    op.drop_table("payment_records")
