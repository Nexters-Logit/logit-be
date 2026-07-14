"""암호화 유틸리티 — 앱 레벨 필드 암호화."""

import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

logger = logging.getLogger(__name__)


class EncryptedString(TypeDecorator):
    """Fernet 대칭 암호화를 사용하는 SQLAlchemy 컬럼 타입.

    PHONE_ENCRYPTION_KEY 설정 시 저장/조회 시 자동 암호화/복호화.
    키가 없으면 평문으로 저장 (개발 환경용).
    """

    impl = String
    cache_ok = True

    def _get_cipher(self) -> Fernet | None:
        from src.config import settings  # 순환 import 방지
        key = settings.PHONE_ENCRYPTION_KEY
        if not key:
            return None
        return Fernet(key.encode())

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        cipher = self._get_cipher()
        if cipher is None:
            return value
        return cipher.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        cipher = self._get_cipher()
        if cipher is None:
            return value
        try:
            return cipher.decrypt(value.encode()).decode()
        except InvalidToken:
            logger.warning("전화번호 복호화 실패 — 평문으로 반환")
            return value
