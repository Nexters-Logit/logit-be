"""remove free_trial from subscriptionplan enum

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-13

free_trial은 구독 플랜이 아닌 기본 상태(구독 레코드 없음)로 표현한다.
subscriptions 테이블에 free_trial 레코드가 있는 경우 삭제 후 실행할 것.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # free_trial 레코드가 남아 있으면 제거 (구독 레코드 없음 = 프리 티어)
    op.execute("DELETE FROM subscriptions WHERE plan = 'free_trial'")

    # PostgreSQL enum 값 제거: 새 타입 생성 → 컬럼 교체 → 구 타입 삭제
    op.execute("ALTER TYPE subscriptionplan RENAME TO subscriptionplan_old")
    op.execute("CREATE TYPE subscriptionplan AS ENUM ('basic', 'lite', 'pro')")
    op.execute(
        "ALTER TABLE subscriptions "
        "ALTER COLUMN plan TYPE subscriptionplan "
        "USING plan::text::subscriptionplan"
    )
    op.execute("DROP TYPE subscriptionplan_old")


def downgrade() -> None:
    op.execute("ALTER TYPE subscriptionplan RENAME TO subscriptionplan_old")
    op.execute("CREATE TYPE subscriptionplan AS ENUM ('free_trial', 'basic', 'lite', 'pro')")
    op.execute(
        "ALTER TABLE subscriptions "
        "ALTER COLUMN plan TYPE subscriptionplan "
        "USING plan::text::subscriptionplan"
    )
    op.execute("DROP TYPE subscriptionplan_old")
