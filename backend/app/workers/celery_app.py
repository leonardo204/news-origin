"""
# celery_app.py - Celery Application Configuration
# Version: 0.1.0
# Description: Celery 비동기 태스크 큐 설정
# Changes:
#   - 0.1.0: Redis broker, 기본 설정
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "newsorigin",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10분 제한
    task_soft_time_limit=540,  # 9분 소프트 제한
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
)
