"""add plans table

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-06-13 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "i4j5k6l7m8n9"
down_revision = "h3i4j5k6l7m8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("subscription_type", sa.String(20), nullable=False),
        sa.Column("plan_key", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("original_price", sa.Integer, nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("badge", sa.String(100), nullable=True),
        sa.Column("features", sa.JSON, nullable=True),
        sa.Column("is_recommended", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_free", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
    )

    plans_table = sa.table(
        "plans",
        sa.column("id", sa.String),
        sa.column("subscription_type", sa.String),
        sa.column("plan_key", sa.String),
        sa.column("name", sa.String),
        sa.column("original_price", sa.Integer),
        sa.column("price", sa.Integer),
        sa.column("description", sa.Text),
        sa.column("badge", sa.String),
        sa.column("features", sa.JSON),
        sa.column("is_recommended", sa.Boolean),
        sa.column("is_free", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("display_order", sa.Integer),
    )

    op.bulk_insert(
        plans_table,
        [
            {
                "id": "logit:lite",
                "subscription_type": "logit",
                "plan_key": "lite",
                "name": "Lite",
                "original_price": 9900,
                "price": 6900,
                "description": "자기소개서 준비를 본격적으로 시작하는 분께",
                "badge": "가장 많이 선택해요",
                "features": ["월 초안 생성 10회", "AI 채팅 50회", "Free의 모든 기능"],
                "is_recommended": True,
                "is_free": False,
                "is_active": True,
                "display_order": 1,
            },
            {
                "id": "logit:pro",
                "subscription_type": "logit",
                "plan_key": "pro",
                "name": "Pro",
                "original_price": 19900,
                "price": 14900,
                "description": "제한 없이 Logit의 모든 기능을 활용하고 싶은 분께",
                "badge": "전체 무제한",
                "features": ["초안 생성 무제한", "AI 채팅 무제한", "Lite의 모든 기능"],
                "is_recommended": False,
                "is_free": False,
                "is_active": True,
                "display_order": 2,
            },
            {
                "id": "mcp:basic",
                "subscription_type": "mcp",
                "plan_key": "basic",
                "name": "Logit MCP",
                "original_price": 3900,
                "price": 1000,
                "description": "Claude, Cursor 등에서 내 경험 데이터를 바로 활용하세요",
                "badge": "출시 할인",
                "features": ["MCP로 내 경험 데이터 연결", "지원 도구에서 경험 검색 및 활용", "월 3,900원에서 1,000원 특별 할인"],
                "is_recommended": False,
                "is_free": False,
                "is_active": True,
                "display_order": 3,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("plans")
