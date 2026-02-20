"""
# admin.py - Admin Dashboard API Routes
# Version: 0.1.0
# Description: 관리자 대시보드 엔드포인트 (인증, 시스템 현황, 크롤링 통계, MLOps, 로그)
# Changes:
#   - 0.1.0: 초기 구현 — login, verify, overview, crawl, mlops, system, stats, logs, settings
"""

import asyncio
import collections
import logging
import platform
import sys
from datetime import datetime, timedelta, timezone

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.auth import authenticate, create_token, require_admin
from app.config import get_settings
from app.models.article import Article
from app.models.base import async_session_factory
from app.models.ner_training import NerModelVersion, NerTrainingSample
from app.models.search_log import SearchLog
from app.models.timeline import TrackingRequest
from app.workers.beat_schedule import (
    CATEGORY_FEEDS,
    FEED_LIMIT_PER_CATEGORY,
    PUBLISHER_FEED_LIMIT,
    PUBLISHER_FEEDS,
)

from sqlalchemy import case, cast, Date, func, select, text

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory log handler (ring buffer)
# ---------------------------------------------------------------------------

class MemoryLogHandler(logging.Handler):
    """최근 로그를 메모리 링 버퍼에 보관하는 핸들러"""

    def __init__(self, maxlen: int = 1000):
        super().__init__()
        self.buffer: collections.deque[dict] = collections.deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append({
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
        except Exception:
            self.handleError(record)


# 모듈 로드 시 루트 로거에 설치
_memory_handler = MemoryLogHandler(maxlen=1000)
_memory_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_memory_handler)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(body: LoginRequest):
    """관리자 로그인 — JWT 토큰 발급"""
    if not authenticate(body.username, body.password):
        raise HTTPException(status_code=401, detail="잘못된 인증 정보입니다")
    token, expires_at = create_token(body.username)
    return {"token": token, "expires_at": expires_at.isoformat()}


@router.get("/verify")
async def verify(username: str = Depends(require_admin)):
    """JWT 토큰 유효성 확인"""
    return {"valid": True, "username": username}


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def overview(username: str = Depends(require_admin)):
    """대시보드 종합 현황"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    # -- articles --
    articles_info: dict = {"total": 0, "today": 0, "this_week": 0, "embedded_rate": 0.0}
    try:
        async with async_session_factory() as session:
            row = await session.execute(
                select(
                    func.count(Article.id).label("total"),
                    func.count(Article.qdrant_point_id).label("embedded"),
                    func.count(case((Article.created_at >= today_start, Article.id))).label("today"),
                    func.count(case((Article.created_at >= week_start, Article.id))).label("this_week"),
                )
            )
            r = row.one()
            total = r.total or 0
            embedded = r.embedded or 0
            articles_info = {
                "total": total,
                "today": r.today or 0,
                "this_week": r.this_week or 0,
                "embedded_rate": round(embedded / total * 100, 1) if total > 0 else 0.0,
            }
    except Exception as e:
        logger.warning(f"overview articles query failed: {e}")

    # -- crawl status --
    crawl_info: dict = {"status": "unknown", "last_run": None, "next_run": None, "articles_per_hour": 0.0}
    try:
        from app.services.cache import get_crawl_status
        cs = await get_crawl_status()
        crawl_info["status"] = cs.get("phase", "idle")
        crawl_info["last_run"] = cs.get("updated_at")

        # articles per hour (last 24h)
        async with async_session_factory() as session:
            h24 = now - timedelta(hours=24)
            row = await session.execute(
                select(func.count(Article.id)).where(Article.created_at >= h24)
            )
            count_24h = row.scalar() or 0
            crawl_info["articles_per_hour"] = round(count_24h / 24, 1)
    except Exception as e:
        logger.warning(f"overview crawl query failed: {e}")

    # -- system --
    system_info: dict = {"cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0}
    try:
        system_info = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except Exception as e:
        logger.warning(f"overview system stats failed: {e}")

    # -- services health --
    services: dict = {"database": "unknown", "redis": "unknown", "qdrant": "unknown", "celery": "unknown"}
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        services["database"] = "ok"
    except Exception:
        services["database"] = "error"

    try:
        from app.services.cache import is_redis_available
        services["redis"] = "ok" if await is_redis_available() else "error"
    except Exception:
        services["redis"] = "error"

    try:
        from app.services.vector_store import is_qdrant_available
        services["qdrant"] = "ok" if await is_qdrant_available() else "error"
    except Exception:
        services["qdrant"] = "error"

    try:
        from app.workers.celery_app import celery_app
        pong = await asyncio.to_thread(celery_app.control.inspect(timeout=2).ping)
        services["celery"] = "ok" if pong else "error"
    except Exception:
        services["celery"] = "error"

    return {
        "articles": articles_info,
        "crawl": crawl_info,
        "system": system_info,
        "services": services,
    }


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------

@router.get("/crawl")
async def crawl(username: str = Depends(require_admin)):
    """크롤링 현황 및 통계"""
    now = datetime.now(timezone.utc)

    schedule = {
        "interval_minutes": 30,
        "categories": list(CATEGORY_FEEDS.keys()),
    }

    category_stats: list[dict] = []
    publisher_stats: list[dict] = []
    recent_articles: list[dict] = []
    daily_counts: list[dict] = []

    try:
        async with async_session_factory() as session:
            # category stats
            row = await session.execute(
                select(
                    Article.metadata_["category"].astext.label("category"),
                    func.count(Article.id).label("count"),
                )
                .where(Article.metadata_["category"].astext.isnot(None))
                .group_by(Article.metadata_["category"].astext)
                .order_by(func.count(Article.id).desc())
            )
            category_stats = [{"category": r.category, "count": r.count} for r in row.all()]

            # publisher stats (top 20)
            row = await session.execute(
                select(
                    Article.publisher,
                    func.count(Article.id).label("count"),
                )
                .where(Article.publisher.isnot(None))
                .group_by(Article.publisher)
                .order_by(func.count(Article.id).desc())
                .limit(20)
            )
            publisher_stats = [{"publisher": r.publisher, "count": r.count} for r in row.all()]

            # recent articles (last 20)
            row = await session.execute(
                select(
                    Article.title,
                    Article.publisher,
                    Article.metadata_["category"].astext.label("category"),
                    Article.created_at,
                )
                .order_by(Article.created_at.desc())
                .limit(20)
            )
            recent_articles = [
                {
                    "title": r.title,
                    "publisher": r.publisher,
                    "category": r.category,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in row.all()
            ]

            # daily counts (last 14 days)
            cutoff = now - timedelta(days=14)
            row = await session.execute(
                select(
                    cast(Article.created_at, Date).label("date"),
                    func.count(Article.id).label("count"),
                )
                .where(Article.created_at >= cutoff)
                .group_by(cast(Article.created_at, Date))
                .order_by(cast(Article.created_at, Date))
            )
            daily_counts = [
                {"date": r.date.isoformat(), "count": r.count}
                for r in row.all()
            ]
    except Exception as e:
        logger.warning(f"crawl stats query failed: {e}")

    return {
        "schedule": schedule,
        "category_stats": category_stats,
        "publisher_stats": publisher_stats,
        "recent_articles": recent_articles,
        "daily_counts": daily_counts,
    }


# ---------------------------------------------------------------------------
# MLOps
# ---------------------------------------------------------------------------

@router.get("/mlops")
async def mlops(username: str = Depends(require_admin)):
    """NER MLOps 파이프라인 현황"""
    settings = get_settings()

    current_model: dict | None = None
    training_data: dict = {"total": 0, "unused": 0, "avg_quality": 0.0}
    model_versions: list[dict] = []

    try:
        async with async_session_factory() as session:
            # current active model
            row = await session.execute(
                select(NerModelVersion).where(NerModelVersion.is_active.is_(True)).limit(1)
            )
            active = row.scalar_one_or_none()
            if active:
                current_model = {
                    "version": active.version,
                    "base_model": active.base_model,
                    "f1": active.eval_f1_score,
                    "is_active": True,
                }

            # training data stats
            row = await session.execute(
                select(
                    func.count(NerTrainingSample.id).label("total"),
                    func.count(
                        case((NerTrainingSample.is_used_for_training.is_(False), NerTrainingSample.id))
                    ).label("unused"),
                    func.avg(NerTrainingSample.gpt_quality_score).label("avg_quality"),
                )
            )
            r = row.one()
            training_data = {
                "total": r.total or 0,
                "unused": r.unused or 0,
                "avg_quality": round(float(r.avg_quality), 3) if r.avg_quality else 0.0,
            }

            # all model versions
            row = await session.execute(
                select(NerModelVersion).order_by(NerModelVersion.created_at.desc())
            )
            model_versions = [
                {
                    "version": m.version,
                    "base_model": m.base_model,
                    "f1": m.eval_f1_score,
                    "precision": m.eval_precision,
                    "recall": m.eval_recall,
                    "status": m.status,
                    "samples": m.training_samples_count,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in row.scalars().all()
            ]
    except Exception as e:
        logger.warning(f"mlops query failed: {e}")

    return {
        "current_model": current_model,
        "training_data": training_data,
        "model_versions": model_versions,
        "config": {
            "min_quality": settings.ner_eval_min_quality,
            "min_samples": settings.ner_training_min_samples,
            "eval_sample_size": settings.ner_eval_sample_size,
        },
    }


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@router.get("/system")
async def system_info(username: str = Depends(require_admin)):
    """호스트 시스템 리소스 현황"""
    try:
        boot_time = psutil.boot_time()
        uptime = datetime.now(timezone.utc).timestamp() - boot_time

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        freq = psutil.cpu_freq()

        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "uptime_seconds": round(uptime, 1),
            "cpu": {
                "percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(logical=True),
                "freq_mhz": round(freq.current, 1) if freq else 0.0,
            },
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "percent": mem.percent,
                "available_gb": round(mem.available / (1024 ** 3), 2),
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "percent": disk.percent,
                "free_gb": round(disk.free / (1024 ** 3), 2),
            },
            "python_version": sys.version,
        }
    except Exception as e:
        logger.warning(f"system info failed: {e}")
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "uptime_seconds": 0.0,
            "cpu": {"percent": 0.0, "count": 0, "freq_mhz": 0.0},
            "memory": {"total_gb": 0.0, "used_gb": 0.0, "percent": 0.0, "available_gb": 0.0},
            "disk": {"total_gb": 0.0, "used_gb": 0.0, "percent": 0.0, "free_gb": 0.0},
            "python_version": sys.version,
        }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def stats(username: str = Depends(require_admin)):
    """기사 및 추적 통계"""
    now = datetime.now(timezone.utc)

    overview_data: dict = {"total_articles": 0, "total_publishers": 0, "total_tracking": 0, "total_searches": 0}
    articles_by_date: list[dict] = []
    articles_by_category: list[dict] = []
    top_publishers: list[dict] = []
    tracking_by_type: dict = {"instant": 0, "live": 0}

    try:
        async with async_session_factory() as session:
            # overview counts
            total_articles = (await session.execute(select(func.count(Article.id)))).scalar() or 0
            total_publishers = (await session.execute(
                select(func.count(func.distinct(Article.publisher)))
            )).scalar() or 0
            total_tracking = (await session.execute(select(func.count(TrackingRequest.id)))).scalar() or 0
            total_searches = (await session.execute(select(func.count(SearchLog.id)))).scalar() or 0
            overview_data = {
                "total_articles": total_articles,
                "total_publishers": total_publishers,
                "total_tracking": total_tracking,
                "total_searches": total_searches,
            }

            # articles by date (last 30 days)
            cutoff_30d = now - timedelta(days=30)
            row = await session.execute(
                select(
                    cast(Article.created_at, Date).label("date"),
                    func.count(Article.id).label("count"),
                )
                .where(Article.created_at >= cutoff_30d)
                .group_by(cast(Article.created_at, Date))
                .order_by(cast(Article.created_at, Date))
            )
            articles_by_date = [{"date": r.date.isoformat(), "count": r.count} for r in row.all()]

            # articles by category
            row = await session.execute(
                select(
                    Article.metadata_["category"].astext.label("category"),
                    func.count(Article.id).label("count"),
                )
                .where(Article.metadata_["category"].astext.isnot(None))
                .group_by(Article.metadata_["category"].astext)
                .order_by(func.count(Article.id).desc())
            )
            articles_by_category = [{"category": r.category, "count": r.count} for r in row.all()]

            # top publishers (top 15)
            row = await session.execute(
                select(
                    Article.publisher,
                    func.count(Article.id).label("count"),
                )
                .where(Article.publisher.isnot(None))
                .group_by(Article.publisher)
                .order_by(func.count(Article.id).desc())
                .limit(15)
            )
            top_publishers = [{"publisher": r.publisher, "count": r.count} for r in row.all()]

            # tracking by type
            row = await session.execute(
                select(
                    TrackingRequest.tracking_type,
                    func.count(TrackingRequest.id).label("count"),
                )
                .group_by(TrackingRequest.tracking_type)
            )
            for r in row.all():
                if r.tracking_type in tracking_by_type:
                    tracking_by_type[r.tracking_type] = r.count
    except Exception as e:
        logger.warning(f"stats query failed: {e}")

    return {
        "overview": overview_data,
        "articles_by_date": articles_by_date,
        "articles_by_category": articles_by_category,
        "top_publishers": top_publishers,
        "tracking_by_type": tracking_by_type,
    }


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@router.get("/logs")
async def logs(
    username: str = Depends(require_admin),
    level: str | None = Query(None, description="Filter by log level (INFO, WARNING, ERROR, etc.)"),
    limit: int = Query(200, ge=1, le=500, description="Number of log entries to return"),
):
    """애플리케이션 로그 조회 (인메모리 링 버퍼)"""
    entries = list(_memory_handler.buffer)

    if level:
        level_upper = level.upper()
        entries = [e for e in entries if e["level"] == level_upper]

    # most recent first, then apply limit
    entries = list(reversed(entries))[:limit]

    return {"logs": entries, "total": len(entries)}


# ---------------------------------------------------------------------------
# Settings (read-only, secrets masked)
# ---------------------------------------------------------------------------

@router.get("/settings")
async def settings_view(username: str = Depends(require_admin)):
    """현재 설정 조회 (비밀 값 마스킹)"""
    settings = get_settings()

    return {
        "crawling": {
            "interval_minutes": 30,
            "categories": list(CATEGORY_FEEDS.keys()),
            "feed_limit_per_category": FEED_LIMIT_PER_CATEGORY,
            "publisher_feed_limit": PUBLISHER_FEED_LIMIT,
            "publishers": list(PUBLISHER_FEEDS.keys()),
            "crawl_delay_seconds": settings.crawl_delay_seconds,
            "crawl_max_concurrent": settings.crawl_max_concurrent,
            "crawl_timeout": settings.crawl_timeout,
        },
        "clustering": {
            "merge_threshold": 0.52,
            "max_component": 30,
        },
        "embedding": {
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension,
        },
        "mlops": {
            "min_quality": settings.ner_eval_min_quality,
            "min_samples": settings.ner_training_min_samples,
            "eval_sample_size": settings.ner_eval_sample_size,
            "base_model": settings.bert_model_name,
            "reextract_days": settings.ner_reextract_days,
            "max_model_versions": settings.ner_max_model_versions,
        },
        "system": {
            "app_env": settings.app_env,
            "retention_days": settings.article_retention_days,
        },
    }
