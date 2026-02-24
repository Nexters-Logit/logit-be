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

    # enum 타입 생성
    subscriptiontype_enum = sa.Enum('mcp', 'logit', name='subscriptiontype')
    subscriptiontype_enum.create(op.get_bind(), checkfirst=True)

    subscriptionplan_enum = sa.Enum('free_trial', 'basic', 'pro', name='subscriptionplan')
    subscriptionplan_enum.create(op.get_bind(), checkfirst=True)

    # type 컬럼 추가 (enum 타입, 기존 데이터는 모두 mcp)
    op.add_column('subscriptions', sa.Column(
        'type', subscriptiontype_enum, nullable=False, server_default=sa.text("'mcp'"),
    ))

    # plan 컬럼을 String -> Enum으로 변경
    # 1) 기존 server_default 제거 (String 타입 default가 enum 변환을 막으므로)
    op.alter_column(
        'subscriptions', 'plan',
        existing_type=sa.String(50),
        existing_nullable=False,
        server_default=None,
    )
    # 2) 타입 변환
    op.alter_column(
        'subscriptions', 'plan',
        type_=subscriptionplan_enum,
        existing_type=sa.String(50),
        existing_nullable=False,
        postgresql_using="plan::subscriptionplan",
    )
    # 3) 새 default 설정
    op.alter_column(
        'subscriptions', 'plan',
        existing_type=subscriptionplan_enum,
        existing_nullable=False,
        server_default=sa.text("'basic'"),
    )

    # unique 제약을 (user_id, type) 으로 재생성
    op.create_unique_constraint('uq_subscription_user_type', 'subscriptions', ['user_id', 'type'])

    # 인덱스 재생성
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])

    # type server_default 제거 (이후 INSERT는 type을 명시적으로 넣어야 함)
    op.alter_column('subscriptions', 'type', server_default=None)


def downgrade() -> None:
    op.alter_column(
        'subscriptions', 'plan',
        type_=sa.String(50),
        existing_type=sa.Enum('free_trial', 'basic', 'pro', name='subscriptionplan'),
        existing_nullable=False,
        server_default=sa.text("'basic'"),
        postgresql_using="plan::text",
    )
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_constraint('uq_subscription_user_type', 'subscriptions', type_='unique')
    op.drop_column('subscriptions', 'type')
    sa.Enum(name='subscriptiontype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='subscriptionplan').drop(op.get_bind(), checkfirst=True)
    op.create_unique_constraint('mcp_subscriptions_user_id_key', 'subscriptions', ['user_id'])
    op.create_index('ix_mcp_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.rename_table('subscriptions', 'mcp_subscriptions')
