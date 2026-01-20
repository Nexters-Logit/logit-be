"""
Dev 환경용 테스트 유저 및 토큰 생성 스크립트

사용법:
    python scripts/create_dev_user.py

출력:
    - 테스트 유저 정보
    - 만료되지 않는 Access Token
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import async_engine
from src.users.models import OAuthProvider


# Dev 테스트 유저 설정
DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_EMAIL = "dev@logit.test"
DEV_USER_NAME = "Dev Test User"


def create_dev_token() -> str:
    """만료되지 않는 (100년) Access Token 생성"""
    expire = datetime.now(timezone.utc) + timedelta(days=36500)  # 100년
    to_encode = {
        "exp": expire,
        "sub": str(DEV_USER_ID),
        "type": "access"
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def create_dev_user():
    """Dev 테스트 유저 생성 (이미 있으면 스킵)"""
    async with AsyncSession(async_engine) as session:
        # 기존 유저 확인
        result = await session.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": str(DEV_USER_ID)}
        )
        existing = result.fetchone()

        if existing:
            print(f"✓ Dev 유저가 이미 존재합니다: {DEV_USER_EMAIL}")
        else:
            # 새 유저 생성
            now = datetime.now(timezone.utc)
            await session.execute(
                text("""
                    INSERT INTO users (
                        id, email, full_name, oauth_provider, oauth_provider_id,
                        is_active, terms_agreed, terms_agreed_at, created_at, updated_at
                    ) VALUES (
                        :id, :email, :full_name, :oauth_provider, :oauth_provider_id,
                        :is_active, :terms_agreed, :terms_agreed_at, :created_at, :updated_at
                    )
                """),
                {
                    "id": str(DEV_USER_ID),
                    "email": DEV_USER_EMAIL,
                    "full_name": DEV_USER_NAME,
                    "oauth_provider": "GOOGLE",
                    "oauth_provider_id": "dev-test-user",
                    "is_active": True,
                    "terms_agreed": True,
                    "terms_agreed_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.commit()
            print(f"✓ Dev 유저 생성 완료: {DEV_USER_EMAIL}")

        # 토큰 생성
        token = create_dev_token()

        print("\n" + "=" * 60)
        print("DEV 테스트 유저 정보")
        print("=" * 60)
        print(f"User ID:  {DEV_USER_ID}")
        print(f"Email:    {DEV_USER_EMAIL}")
        print(f"Name:     {DEV_USER_NAME}")
        print("\n" + "-" * 60)
        print("ACCESS TOKEN (만료: 100년 후)")
        print("-" * 60)
        print(token)
        print("=" * 60)

        return token


if __name__ == "__main__":
    if settings.ENVIRONMENT == "production":
        print("❌ 프로덕션 환경에서는 실행할 수 없습니다!")
        sys.exit(1)

    asyncio.run(create_dev_user())
