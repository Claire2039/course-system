"""应用配置：从环境变量（或 .env）加载。M0 仅读取；DB/Redis/MinIO 客户端在 M1+ 接入。"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://course:change_me@localhost:5432/coursedb"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "courses"
    minio_secure: bool = False

    # Session（M2 认证使用）
    # 注：采用 opaque 随机 sid + Redis 权威的设计，不签名 cookie，故 session_secret 当前未使用（预留）。
    session_secret: str = "dev-insecure-change-me"
    session_cookie_name: str = "session"
    session_cookie_domain: str = ""
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 天

    # CORS（环境变量传 JSON 数组，如 CORS_ORIGINS='["http://localhost:3000"]'）
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:3000"]
    )


settings = Settings()
