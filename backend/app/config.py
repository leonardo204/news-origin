"""
# config.py - Application Configuration
# Version: 0.1.0
# Description: Pydantic Settings 기반 환경변수 관리
# Changes:
#   - 0.1.0: Initial configuration with DB, Qdrant, Redis, crawling settings
"""

import logging
import warnings

from pydantic_settings import BaseSettings
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    애플리케이션 전역 설정

    [BUSINESS LOGIC - DO NOT MODIFY]
    환경변수 로딩 순서: .env 파일 → 시스템 환경변수 (시스템이 우선)
    """

    # App
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"
    cors_origins: str = "http://localhost:10080,http://localhost:15173"

    # Database
    database_url: str = "postgresql+asyncpg://newsorigin:newsorigin_dev_password@localhost:15432/newsorigin"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 16333
    qdrant_grpc_port: int = 16334
    qdrant_collection: str = "article_embeddings"

    # Redis
    redis_url: str = "redis://localhost:16379/0"
    celery_broker_url: str = "redis://localhost:16379/1"

    # Embedding
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    embedding_dimension: int = 768

    # News APIs
    gnews_api_key: str = ""

    # Crawling
    crawl_delay_seconds: float = 2.0
    crawl_max_concurrent: int = 5
    crawl_user_agent: str = "NewsOrigin/0.1 (Research Bot)"

    # Similarity thresholds
    similarity_same_threshold: float = 0.90
    similarity_derivative_threshold: float = 0.75
    similarity_related_threshold: float = 0.50

    # Background Crawling
    background_crawl_enabled: bool = True
    article_retention_days: int = 90

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def validate_startup(self) -> None:
        """서버 시작 시 설정값 검증"""
        if self.app_env != "development" and self.app_secret_key == "change-me-in-production":
            raise ValueError("프로덕션 환경에서는 APP_SECRET_KEY를 변경해야 합니다.")
        if self.app_env == "development" and self.app_secret_key == "change-me-in-production":
            warnings.warn("APP_SECRET_KEY가 기본값입니다. 프로덕션 배포 전 변경하세요.", stacklevel=2)
        if not self.database_url:
            raise ValueError("DATABASE_URL이 설정되지 않았습니다.")
        if self.similarity_same_threshold <= self.similarity_derivative_threshold:
            warnings.warn("similarity_same_threshold가 derivative보다 낮습니다.", stacklevel=2)


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_startup()
    return settings
