"""채팅 레이트 리밋 모듈"""

from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis

from src.config import settings


class ChatRateLimiter:
    """일일 채팅 횟수 제한 관리"""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.daily_limit = settings.CHAT_DAILY_LIMIT

    def _get_key(self, user_id: UUID) -> str:
        """Redis 키 생성: chat_limit:{user_id}:{date}"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"chat_limit:{user_id}:{today}"

    def _get_ttl_seconds(self) -> int:
        """자정까지 남은 초 계산"""
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # 다음 날로 이동
        if now >= tomorrow:
            from datetime import timedelta
            tomorrow += timedelta(days=1)
        return int((tomorrow - now).total_seconds()) + 1

    async def check_limit(self, user_id: UUID) -> tuple[bool, int]:
        """
        채팅 제한 확인

        Returns:
            tuple[bool, int]: (허용 여부, 남은 횟수)
        """
        key = self._get_key(user_id)
        current = await self.redis.get(key)

        if current is None:
            return True, self.daily_limit

        count = int(current)
        remaining = self.daily_limit - count

        return remaining > 0, max(0, remaining)

    async def increment(self, user_id: UUID) -> int:
        """
        채팅 횟수 증가

        Returns:
            int: 현재 사용 횟수
        """
        key = self._get_key(user_id)

        # INCR + EXPIRE를 atomic하게 처리
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self._get_ttl_seconds())
        results = await pipe.execute()

        return results[0]  # INCR 결과 (현재 카운트)

    async def get_remaining(self, user_id: UUID) -> int:
        """남은 채팅 횟수 조회"""
        key = self._get_key(user_id)
        current = await self.redis.get(key)

        if current is None:
            return self.daily_limit

        return max(0, self.daily_limit - int(current))
