"""add is_completed to questions

Revision ID: a1b2c3d4e5f6
Revises: 41cefd1e6e04
Create Date: 2026-02-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '41cefd1e6e04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index('ix_questions_is_completed', 'questions', ['is_completed'])


def downgrade() -> None:
    op.drop_index('ix_questions_is_completed', table_name='questions')
    op.drop_column('questions', 'is_completed')
