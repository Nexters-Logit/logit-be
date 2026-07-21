from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    """Parse CORS origins from string or list"""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Logit API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["local", "dev", "production"] = "local"

    # Docs Authentication (for dev environment)
    DOCS_USERNAME: str = "admin"
    DOCS_PASSWORD: str = "admin"  # Override in .env for dev

    # Security - JWT Token Settings
    SECRET_KEY: str  # Must be set in .env!

    # Access token: short-lived
    # - Web: 15-30 minutes (requires frequent refresh)
    # - Mobile: 1-24 hours (better UX, acceptable for mobile apps)
    # Can be overridden in .env: ACCESS_TOKEN_EXPIRE_MINUTES=60
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes default

    # Refresh token: long-lived but rotated on each use
    # - OAuth 2.0 BCP recommends rotation for security
    # - Longer expiry is safer with rotation (prevents session loss)
    # Can be overridden in .env: REFRESH_TOKEN_EXPIRE_DAYS=60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days default

    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []
    BACKEND_HOST: str = "http://localhost:8000"
    FRONTEND_HOST: str = "http://localhost:3000"

    @computed_field
    @property
    def all_cors_origins(self) -> list[str]:
        origins = [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]
        # dev 환경에서는 localhost:3000도 허용 (프론트 로컬 개발용)
        if self.ENVIRONMENT == "dev" and "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        return origins

    # Database - PostgreSQL
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """Async database URI (for future async operations)."""
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # Redis
    REDIS_URL: str

    # Qdrant Vector Database (production-grade, cost-efficient)
    QDRANT_HOST: str
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "logit_embeddings"

    # OAuth - Google
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_IOS_CLIENT_ID: str | None = None
    GOOGLE_ANDROID_CLIENT_ID: str | None = None

    # OAuth - Apple
    APPLE_CLIENT_ID: str | None = None   # 웹용 Service ID (예: kr.ai.logit.web)
    APPLE_BUNDLE_ID: str | None = None   # iOS 앱 Bundle ID (예: kr.ai.logit)
    APPLE_TEAM_ID: str | None = None
    APPLE_KEY_ID: str | None = None
    APPLE_PRIVATE_KEY: str | None = None

    # OpenAI (for Langchain)
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.7

    # Anthropic (for writing tasks)
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # MCP
    MCP_JWT_SECRET: str
    MCP_TOKEN_EXPIRE_DAYS: int = 30

    # Test User IDs (채팅 제한 면제)
    TEST_USER_IDS: list[str] = []

    # PayApp 결제
    PAYAPP_USERID: str | None = None
    PAYAPP_LINKKEY: str | None = None
    PAYAPP_LINKVAL: str | None = None
    PAYAPP_CALLBACK_URL: str = "http://localhost:8000/api/v1/payments/webhook"
    FRONTEND_URL: str = "http://localhost:3000"

    # 전화번호 암호화 키 (Fernet URL-safe base64 32바이트 키)
    # 생성: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # 미설정 시 평문 저장 (로컬 개발용)
    PHONE_ENCRYPTION_KEY: str | None = None

    # Admin internal API secret (어드민 서버에서 내부 API 호출 시 사용)
    ADMIN_SECRET: str | None = None

    # Sentry
    SENTRY_DSN: str | None = None

    # Discord Error Notification
    DISCORD_WEBHOOK_URL: str | None = None

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        """Validate that required secrets are set."""
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in .env")
        if not self.POSTGRES_PASSWORD:
            raise ValueError("POSTGRES_PASSWORD must be set in .env")
        if self.ENVIRONMENT == "production":
            if self.DOCS_USERNAME == "admin" or self.DOCS_PASSWORD == "admin":
                raise ValueError("DOCS_USERNAME and DOCS_PASSWORD must be changed from defaults in production")
            if not self.ADMIN_SECRET:
                raise ValueError("ADMIN_SECRET must be set in production")
        return self


settings = Settings()
