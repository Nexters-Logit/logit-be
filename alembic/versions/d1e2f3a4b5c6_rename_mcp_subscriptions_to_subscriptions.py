"""rename_mcp_subscriptions_to_subscriptions_with_type

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-02-21 00:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'd1e2f3a4b5c6'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 테이블 이름 변경
    op.rename_table('mcp_subscriptions', 'subscriptions')

    # 기존 인덱스/제약 이름 변경
    op.drop_index('ix_mcp_subscriptions_user_id', table_name='subscriptions')
    op.drop_constraint('mcp_subscriptions_user_id_key', 'subscriptions', type_='unique')

    # type 컬럼 추가 (기존 데이터는 모두 mcp)
    op.add_column('subscriptions', sa.Column('type', sa.String(length=10), nullable=False, server_default='mcp'))

    # unique 제약을 (user_id, type) 으로 재생성
    op.create_unique_constraint('uq_subscription_user_type', 'subscriptions', ['user_id', 'type'])

    # 인덱스 재생성
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])

    # server_default 제거 (이후 INSERT는 type을 명시적으로 넣어야 함)
    op.alter_column('subscriptions', 'type', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_constraint('uq_subscription_user_type', 'subscriptions', type_='unique')
    op.drop_column('subscriptions', 'type')
    op.create_unique_constraint('mcp_subscriptions_user_id_key', 'subscriptions', ['user_id'])
    op.create_index('ix_mcp_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.rename_table('subscriptions', 'mcp_subscriptions')
