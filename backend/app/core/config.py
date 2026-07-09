from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=LOCAL_ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="BID_REVIEW_",
        extra="ignore",
    )

    app_name: str = "投标文件三项审查系统"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://bid_review:bid_review@postgres:5432/bid_review"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    object_storage_endpoint: str = "http://minio:9000"
    object_storage_bucket: str = "bid-review-private"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"

    max_upload_bytes: int = Field(default=500 * 1024 * 1024, ge=1)
    allowed_mime_types: tuple[str, ...] = ("application/pdf",)
    sensitive_hmac_key: str = "local-development-only-change-me"
    readiness_check_dependencies: bool = False

    enable_ocr: bool = False
    enable_llm: bool = False

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    map_reduce_concurrency: int = Field(default=5, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
