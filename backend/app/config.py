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

    # Embedding (Azure OpenAI text-embedding-3-large)
    embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 1024
    azure_openai_embedding_endpoint: str = ""
    azure_openai_embedding_api_key: str = ""
    azure_openai_embedding_deployment_name: str = "text-embedding-3-large"
    azure_openai_embedding_api_version: str = "2024-12-01-preview"

    # Azure OpenAI GPT (평가용)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_model_name: str = "gpt-5"
    azure_openai_api_version: str = "2025-01-01-preview"

    # BERT NER (키워드 추출용)
    bert_model_name: str = "klue/bert-base"
    bert_ner_model_path: str = ""  # fine-tuned 모델 경로 (비어있으면 기본 모델)

    # News APIs
    gnews_api_key: str = ""

    # Crawling
    crawl_delay_seconds: float = 2.0
    crawl_max_concurrent: int = 5
    crawl_user_agent: str = "NewsOrigin/0.1 (Research Bot)"
    crawl_timeout: int = 8
    news_search_timeout: int = 8

    # Similarity thresholds
    similarity_same_threshold: float = 0.90
    similarity_derivative_threshold: float = 0.75
    similarity_related_threshold: float = 0.50

    # Background Crawling
    background_crawl_enabled: bool = True
    article_retention_days: int = 90

    # MLOps - NER Fine-tuning
    ner_model_base_dir: str = "/app/models/bert-ner"
    ner_eval_sample_size: int = 30
    ner_eval_min_quality: float = 0.7
    ner_training_min_samples: int = 200
    ner_reextract_days: int = 7
    ner_max_model_versions: int = 3
    ner_excluded_publishers: list[str] = ["한겨레"]  # AI 학습 금지 명시 언론사

    # Admin Dashboard
    admin_username: str = ""
    admin_password: str = ""
    admin_jwt_expire_hours: int = 24

    # SMTP Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    admin_email: str = ""  # 리포트 수신 이메일

    # Alert Thresholds (비정기 리포트 트리거)
    alert_error_rate_threshold: float = 10.0  # 에러율 N% 이상
    alert_traffic_spike_multiplier: float = 3.0  # 트래픽 N배 급증
    alert_disk_usage_threshold: float = 90.0  # 디스크 사용률 N% 이상
    alert_memory_usage_threshold: float = 90.0  # 메모리 사용률 N% 이상
    alert_cooldown_minutes: int = 60  # 동일 알림 재발송 방지 (분)

    # Webhook
    webhook_url: str = ""  # Discord/Slack webhook URL

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
