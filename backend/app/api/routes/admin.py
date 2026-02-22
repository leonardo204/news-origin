"""
# admin.py - Admin Dashboard API Routes
# Version: 0.6.0
# Description: 관리자 대시보드 엔드포인트 (인증, 시스템 현황, 크롤링 통계, MLOps, 로그)
# Changes:
#   - 0.6.0: /mlops에 finetune_status 추가 — Docker SDK로 finetune 컨테이너 상태/로그 모니터링
#   - 0.5.0: /mlops에 quality_analytics 섹션 추가 (일별 품질 추이, 엔터티 오류, 방식 비율, 인사이트)
#   - 0.4.0: MLOps 고도화 — 인라인 평가 활동, KST 예상 시간, 자동 finetune 상태, 예측 대시보드
#   - 0.3.0: /crawl에 feed_sources 추가, /mlops에 schedule+pipeline 추가
#   - 0.2.0: JSONB GROUP BY 수정, 설정 필드 정합성, 크롤 상태 필드명, 쿼리 독립 실행
#   - 0.1.0: 초기 구현 — login, verify, overview, crawl, mlops, system, stats, logs, settings
"""

import asyncio
import collections
import logging
import platform
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.auth import authenticate, create_token, require_admin
from app.config import get_settings
from app.models.admin_report import AdminReport
from app.models.article import Article
from app.models.base import async_session_factory
from app.models.ner_training import NerModelVersion, NerTrainingSample
from app.models.search_log import SearchLog
from app.models.timeline import TrackingRequest
from app.workers.beat_schedule import (
    CATEGORY_FEEDS,
    FEED_LIMIT_PER_CATEGORY,
    MAX_ARTICLES_PER_RUN,
    PUBLISHER_FEED_LIMIT,
    PUBLISHER_FEEDS,
)

from sqlalchemy import case, cast, Date, func, literal_column, select, text

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_finetune_container_status() -> dict:
    """Docker SDK로 newsorigin-finetune 컨테이너 상태 조회"""
    try:
        import docker
    except ImportError:
        return {"status": "unavailable", "error": "docker SDK not installed"}

    try:
        client = docker.from_env(timeout=5)
        container = client.containers.get("newsorigin-finetune")
        state = container.attrs.get("State", {})

        result: dict = {
            "status": container.status,  # running, exited, created, etc.
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
            "exit_code": state.get("ExitCode"),
        }

        # 로그 마지막 10줄
        try:
            logs = container.logs(tail=10, timestamps=False).decode("utf-8", errors="replace")
            result["logs_tail"] = logs.strip().split("\n") if logs.strip() else []
        except Exception:
            result["logs_tail"] = []

        return result

    except Exception as e:
        err_type = type(e).__name__
        if "NotFound" in err_type:
            return {"status": "not_found"}
        return {"status": "error", "error": str(e)[:200]}

# 카테고리 한글 라벨 매핑
CATEGORY_LABELS = {
    "headlines": "헤드라인",
    "politics": "정치",
    "economy": "경제",
    "society": "사회",
    "tech": "기술",
    "entertainment": "연예",
    "sports": "스포츠",
    "world": "세계",
}

# KST 타임존 (UTC+9)
KST = timezone(timedelta(hours=9))


def _next_cron_run(*, minute: str | int = 0, hour: str | int = "*",
                   day_of_month: str | int = "*", day_of_week: str | int = "*") -> str:
    """간단한 cron 패턴으로 다음 실행 시각을 KST 문자열로 반환 (입력값은 KST 기준)

    Beat 스케줄이 timezone="Asia/Seoul"이므로 crontab 값이 KST 기준.
    이 함수도 KST 기준으로 계산해야 beat와 일치.
    """
    now_kst = datetime.now(KST)

    def _expand(pattern: str | int, max_val: int) -> set[int]:
        if isinstance(pattern, int):
            return {pattern}
        if pattern == "*":
            return set(range(max_val))
        if pattern.startswith("*/"):
            step = int(pattern[2:])
            return set(range(0, max_val, step))
        return {int(pattern)}

    min_vals = _expand(minute, 60)
    hr_vals = _expand(hour, 24)
    dom_check = None if day_of_month == "*" else _expand(day_of_month, 32)
    dow_check = None if day_of_week == "*" else _expand(day_of_week, 7)

    # 다음 실행 시각 찾기 (최대 31일 내, KST 기준)
    candidate = now_kst.replace(second=0, microsecond=0)
    for _ in range(31 * 24 * 60):
        candidate += timedelta(minutes=1)
        if candidate.minute not in min_vals:
            continue
        if candidate.hour not in hr_vals:
            continue
        if dom_check is not None and candidate.day not in dom_check:
            continue
        if dow_check is not None and candidate.weekday() not in dow_check:
            continue
        return candidate.strftime("%m/%d %H:%M KST")

    return "계산 불가"


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
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone(ZoneInfo("Asia/Seoul")).strftime("%m/%d %H:%M:%S KST"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
        except Exception:
            self.handleError(record)


# setup_logging() 이후 호출해야 핸들러가 유지됨 (main.py에서 init_log_handler() 호출)
_memory_handler = MemoryLogHandler(maxlen=1000)
_memory_handler.setFormatter(logging.Formatter("%(message)s"))


def init_log_handler() -> None:
    """루트 로거에 메모리 핸들러 추가 — setup_logging() 이후 호출"""
    root = logging.getLogger()
    if _memory_handler not in root.handlers:
        root.addHandler(_memory_handler)


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
        crawl_info["last_run"] = cs.get("started_at")

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
        if pong:
            services["celery"] = "ok"
        else:
            # solo pool can't respond to inspect while busy; check Redis heartbeat fallback
            from app.services.cache import get_redis
            _r = await get_redis()
            if _r and await _r.exists("celery:worker:heartbeat"):
                services["celery"] = "ok"
            else:
                services["celery"] = "error"
    except Exception:
        services["celery"] = "error"

    # -- traffic summary --
    traffic_info: dict = {
        "today": 0, "error_rate": 0.0, "avg_duration": 0.0, "unique_ips": 0,
    }
    try:
        from app.models.request_log import RequestLog

        async with async_session_factory() as session:
            cutoff_30d = now - timedelta(days=30)
            row = await session.execute(
                select(
                    func.count(case((RequestLog.created_at >= today_start, RequestLog.id))).label("today"),
                    func.avg(case((RequestLog.created_at >= cutoff_30d, RequestLog.duration_ms))).label("avg_dur"),
                    func.count(case((
                        (RequestLog.created_at >= cutoff_30d) & (RequestLog.status_code >= 400),
                        RequestLog.id,
                    ))).label("errors"),
                    func.count(case((RequestLog.created_at >= cutoff_30d, RequestLog.id))).label("total"),
                    func.count(func.distinct(case((RequestLog.created_at >= cutoff_30d, RequestLog.client_ip)))).label("unique_ips"),
                )
            )
            r = row.one()
            total = r.total or 0
            traffic_info = {
                "today": r.today or 0,
                "error_rate": round((r.errors or 0) / total * 100, 1) if total > 0 else 0.0,
                "avg_duration": round(float(r.avg_dur), 1) if r.avg_dur else 0.0,
                "unique_ips": r.unique_ips or 0,
            }
    except Exception as e:
        logger.warning(f"overview traffic query failed: {e}")

    # -- MLOps summary --
    settings = get_settings()
    mlops_info: dict = {
        "model_version": "base", "model_f1": None,
        "training_total": 0, "training_unused": 0,
        "target_samples": settings.ner_training_min_samples,
        "readiness_pct": 0, "avg_quality": 0.0,
    }
    try:
        async with async_session_factory() as session:
            row = await session.execute(
                select(NerModelVersion).where(NerModelVersion.is_active.is_(True)).limit(1)
            )
            active = row.scalar_one_or_none()
            if active:
                mlops_info["model_version"] = active.version
                mlops_info["model_f1"] = active.eval_f1_score

            row = await session.execute(
                select(
                    func.count(NerTrainingSample.id).label("total"),
                    func.count(case((NerTrainingSample.is_used_for_training.is_(False), NerTrainingSample.id))).label("unused"),
                    func.avg(NerTrainingSample.gpt_quality_score).label("avg_quality"),
                )
            )
            r = row.one()
            unused = r.unused or 0
            target = settings.ner_training_min_samples
            mlops_info["training_total"] = r.total or 0
            mlops_info["training_unused"] = unused
            mlops_info["readiness_pct"] = min(100, round(unused / target * 100)) if target > 0 else 0
            mlops_info["avg_quality"] = round(float(r.avg_quality), 3) if r.avg_quality else 0.0
    except Exception as e:
        logger.warning(f"overview mlops query failed: {e}")

    return {
        "articles": articles_info,
        "crawl": crawl_info,
        "system": system_info,
        "services": services,
        "traffic": traffic_info,
        "mlops": mlops_info,
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

    # 각 쿼리를 독립 실행하여 하나의 실패가 전체에 영향 주지 않도록 함
    try:
        async with async_session_factory() as session:
            cat_col = Article.metadata_["category"].astext
            row = await session.execute(
                select(
                    cat_col.label("category"),
                    func.count(Article.id).label("count"),
                )
                .where(cat_col.isnot(None))
                .group_by(literal_column("category"))
                .order_by(func.count(Article.id).desc())
            )
            category_stats = [{"category": r.category, "count": r.count} for r in row.all()]
    except Exception as e:
        logger.warning(f"crawl category_stats query failed: {e}")

    try:
        async with async_session_factory() as session:
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
    except Exception as e:
        logger.warning(f"crawl publisher_stats query failed: {e}")

    try:
        async with async_session_factory() as session:
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
    except Exception as e:
        logger.warning(f"crawl recent_articles query failed: {e}")

    try:
        async with async_session_factory() as session:
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
        logger.warning(f"crawl daily_counts query failed: {e}")

    feed_sources = {
        "categories": [
            {"key": key, "label": CATEGORY_LABELS.get(key, key), "url": url}
            for key, url in CATEGORY_FEEDS.items()
        ],
        "publishers": [
            {"name": name, "url": url}
            for name, url in PUBLISHER_FEEDS.items()
        ],
        "limits": {
            "per_category": FEED_LIMIT_PER_CATEGORY,
            "per_publisher": PUBLISHER_FEED_LIMIT,
            "max_per_run": MAX_ARTICLES_PER_RUN,
        },
    }

    return {
        "schedule": schedule,
        "feed_sources": feed_sources,
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
            else:
                # fine-tuned 모델이 없으면 기본 BERT 모델 정보 표시
                current_model = {
                    "version": "base",
                    "base_model": settings.bert_model_name,
                    "f1": None,
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

    # -- recent evaluations (last 24h) --
    recent_evaluations: list[dict] = []
    daily_eval_count = 0
    try:
        async with async_session_factory() as session:
            cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            # 24시간 내 수집 건수
            cnt_row = await session.execute(
                select(func.count(NerTrainingSample.id)).where(
                    NerTrainingSample.created_at >= cutoff_24h
                )
            )
            daily_eval_count = cnt_row.scalar() or 0

            # 최근 평가 20건 상세
            row = await session.execute(
                select(
                    NerTrainingSample.title,
                    NerTrainingSample.gpt_quality_score,
                    NerTrainingSample.extraction_method,
                    NerTrainingSample.created_at,
                    NerTrainingSample.original_entities,
                    NerTrainingSample.gpt_corrected_entities,
                )
                .where(NerTrainingSample.created_at >= cutoff_24h)
                .order_by(NerTrainingSample.created_at.desc())
                .limit(20)
            )
            recent_evaluations = [
                {
                    "title": r.title[:60] if r.title else "",
                    "quality_score": round(float(r.gpt_quality_score), 2) if r.gpt_quality_score else 0,
                    "method": r.extraction_method or "unknown",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "original_entities": r.original_entities or [],
                    "corrected_entities": r.gpt_corrected_entities or [],
                }
                for r in row.all()
            ]
    except Exception as e:
        logger.warning(f"mlops recent_evaluations query failed: {e}")

    # -- pipeline status --
    min_samples = settings.ner_training_min_samples
    total = training_data["total"]
    unused = training_data["unused"]
    avg_quality = training_data["avg_quality"]
    has_finetuned = len(model_versions) > 0
    active_version = current_model["version"] if current_model else "base"

    # ready 모델 존재 여부 (fine-tuning 완료 but 미배포)
    has_ready_undeployed = any(
        m["status"] == "ready" for m in model_versions
    ) and active_version == "base"

    # stage status 결정
    collect_status = "done" if unused >= min_samples else ("active" if unused > 0 else "waiting")
    readiness_status = "ready" if unused >= min_samples else "collecting"
    finetune_status = "done" if has_finetuned else "waiting"
    deploy_status = (
        "active" if has_finetuned and active_version != "base"
        else "pending" if has_ready_undeployed
        else "waiting"
    )
    remaining = max(0, min_samples - unused)

    pipeline = {
        "stages": [
            {
                "id": "collect", "label": "데이터 수집", "status": collect_status,
                "progress": unused, "target": min_samples,
                "detail": f"{unused}/{min_samples}건",
            },
            {
                "id": "evaluate", "label": "품질 평가", "status": "active",
                "detail": f"평균 품질: {avg_quality:.2f}",
            },
            {
                "id": "readiness", "label": "학습 준비", "status": readiness_status,
                "progress": unused, "target": min_samples,
                "detail": "준비 완료" if readiness_status == "ready" else f"{remaining}건 부족",
            },
            {
                "id": "finetune", "label": "Fine-tuning", "status": finetune_status,
                "detail": f"최신: {model_versions[0]['version']}" if has_finetuned else "자동 트리거 대기",
            },
            {
                "id": "deploy", "label": "모델 배포", "status": deploy_status,
                "detail": (
                    f"활성: {active_version}" if deploy_status == "active"
                    else f"배포 대기: {model_versions[0]['version']}" if deploy_status == "pending"
                    else "대기 중"
                ),
            },
            {
                "id": "reextract", "label": "키워드 재추출", "status": "done" if has_finetuned else "waiting",
                "detail": "모델 승격 시 자동 실행",
            },
            {
                "id": "recluster", "label": "재클러스터링", "status": "waiting",
                "detail": "재추출 후 자동 실행",
            },
        ],
        "summary": {
            "total_samples": total,
            "unused_samples": unused,
            "target_samples": min_samples,
            "readiness_percent": round(unused / min_samples * 100, 1) if min_samples > 0 else 0.0,
            "active_model": active_version,
        },
    }

    # -- predictions --
    est_days_to_ready = None
    if remaining > 0 and daily_eval_count > 0:
        est_days_to_ready = max(1, round(remaining / daily_eval_count))
    elif remaining > 0:
        # fallback: 이론적 수집률 (6h×4 + 30min×48 inline, 품질 통과 ~60%)
        theoretical_daily = (settings.ner_eval_sample_size * 4 + 5 * 48) * 0.6
        est_days_to_ready = max(1, round(remaining / theoretical_daily)) if theoretical_daily > 0 else None

    now_kst = datetime.now(KST)
    predictions = {
        "finetune_ready": unused >= min_samples,
        "daily_collection_rate": daily_eval_count,
        "est_days_to_ready": est_days_to_ready if remaining > 0 else 0,
        "est_ready_date_kst": (
            (now_kst + timedelta(days=est_days_to_ready)).strftime("%Y-%m-%d")
            if est_days_to_ready and remaining > 0 else None
        ),
        "next_finetune_trigger": (
            "임계 도달 → 다음 02:00 KST 자동 실행" if not (unused >= min_samples)
            else "다음 학습 준비 확인 시 자동 트리거"
        ),
        "current_phase": (
            "fine-tuning 대기" if unused >= min_samples
            else "데이터 수집 중"
        ),
        "timestamp_kst": now_kst.strftime("%Y-%m-%d %H:%M KST"),
    }

    # -- quality analytics --
    ENTITY_LABELS = {
        "PS": "인물", "OG": "기관", "LC": "장소",
        "DT": "날짜", "TI": "시간", "QT": "수량",
    }
    quality_analytics: dict = {
        "daily_scores": [],
        "entity_error_types": [],
        "method_ratio": {"bert_ner": 0, "kiwipiepy": 0},
        "latest_insight": None,
    }
    try:
        cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)
        async with async_session_factory() as session:
            # daily_scores (30일)
            rows = await session.execute(
                select(
                    cast(NerTrainingSample.created_at, Date).label("date"),
                    func.avg(NerTrainingSample.gpt_quality_score).label("avg_score"),
                    func.count(NerTrainingSample.id).label("count"),
                    func.count(case((NerTrainingSample.extraction_method == "bert_ner", NerTrainingSample.id))).label("method_bert"),
                    func.count(case((NerTrainingSample.extraction_method == "kiwipiepy", NerTrainingSample.id))).label("method_kiwi"),
                )
                .where(NerTrainingSample.created_at >= cutoff_30d)
                .group_by(cast(NerTrainingSample.created_at, Date))
                .order_by(cast(NerTrainingSample.created_at, Date))
            )
            quality_analytics["daily_scores"] = [
                {
                    "date": r.date.isoformat(),
                    "avg_score": round(float(r.avg_score), 3) if r.avg_score else 0,
                    "count": r.count,
                    "method_bert": r.method_bert,
                    "method_kiwi": r.method_kiwi,
                }
                for r in rows.all()
            ]

            # entity_error_types — gpt_corrected_entities JSONB 순회
            rows = await session.execute(
                select(NerTrainingSample.gpt_corrected_entities)
                .where(NerTrainingSample.created_at >= cutoff_30d)
            )
            type_counts: dict[str, int] = {}
            for (entities,) in rows.all():
                if isinstance(entities, list):
                    for ent in entities:
                        etype = ent.get("type", "UNK") if isinstance(ent, dict) else "UNK"
                        type_counts[etype] = type_counts.get(etype, 0) + 1
            total_entities = sum(type_counts.values()) or 1
            quality_analytics["entity_error_types"] = sorted(
                [
                    {
                        "type": etype,
                        "label": ENTITY_LABELS.get(etype, etype),
                        "count": count,
                        "pct": round(count / total_entities * 100, 1),
                    }
                    for etype, count in type_counts.items()
                ],
                key=lambda x: -x["count"],
            )

            # method_ratio — daily_scores에서 이미 집계된 데이터 재활용
            quality_analytics["method_ratio"] = {
                "bert_ner": sum(r["method_bert"] for r in quality_analytics["daily_scores"]),
                "kiwipiepy": sum(r["method_kiwi"] for r in quality_analytics["daily_scores"]),
            }

            # latest_insight — deployment_insight가 있는 최신 모델
            row = await session.execute(
                select(NerModelVersion)
                .where(NerModelVersion.deployment_insight.isnot(None))
                .order_by(NerModelVersion.created_at.desc())
                .limit(1)
            )
            insight_model = row.scalar_one_or_none()
            if insight_model:
                quality_analytics["latest_insight"] = {
                    "version": insight_model.version,
                    "insight": insight_model.deployment_insight,
                    "created_at": insight_model.created_at.isoformat() if insight_model.created_at else None,
                }
    except Exception as e:
        logger.warning(f"mlops quality_analytics query failed: {e}")

    # -- schedule info (with KST next-run) --
    schedule = [
        {
            "task": "뉴스 수집 + 인라인 평가",
            "interval": "30분마다",
            "detail": "배치당 5건 GPT-5 평가",
            "next_run_kst": _next_cron_run(minute="*/30"),
        },
        {
            "task": "데이터 수집 (GPT-5 평가)",
            "interval": "6시간마다",
            "detail": f"{settings.ner_eval_sample_size}건/회",
            "next_run_kst": _next_cron_run(minute=15, hour="*/6"),
        },
        {
            "task": "학습 준비 확인",
            "interval": "매일 11:00 KST",
            "detail": f"임계값: {settings.ner_training_min_samples}건",
            "next_run_kst": _next_cron_run(minute=0, hour=11),
        },
        {
            "task": "Fine-tuning",
            "interval": "자동 (준비 완료 시)",
            "detail": "임계 도달 시 자동 트리거",
            "next_run_kst": "준비 완료 시" if unused < min_samples else "트리거 대기",
        },
        {
            "task": "키워드 재추출",
            "interval": "매월 1일 04:00 KST",
            "detail": f"최근 {settings.ner_reextract_days}일",
            "next_run_kst": _next_cron_run(minute=0, hour=4, day_of_month=1),
        },
    ]

    # -- finetune container status --
    finetune_status = await asyncio.to_thread(_get_finetune_container_status)

    # pipeline finetune 스테이지에 컨테이너 상태 반영
    if finetune_status.get("status") == "running":
        for stage in pipeline["stages"]:
            if stage["id"] == "finetune":
                stage["status"] = "active"
                stage["detail"] = "컨테이너 학습 중"
                break

    # -- reextract / recluster 스테이지 상태 반영 --
    try:
        from app.services.cache import cache_get
        last_reextract = await cache_get("mlops:last_reextract")
        if last_reextract:
            from datetime import datetime as _dt
            completed_at = last_reextract.get("completed_at", "")
            reextracted = last_reextract.get("reextracted", 0)
            model_ver = last_reextract.get("model_version", "?")
            cache_warmed = last_reextract.get("cache_warmed", False)
            # KST 변환
            try:
                utc_dt = _dt.fromisoformat(completed_at)
                from zoneinfo import ZoneInfo
                kst_str = utc_dt.astimezone(ZoneInfo("Asia/Seoul")).strftime("%m/%d %H:%M")
            except Exception:
                kst_str = ""

            for stage in pipeline["stages"]:
                if stage["id"] == "reextract":
                    stage["status"] = "done"
                    stage["detail"] = f"{reextracted}건 · {model_ver} · {kst_str}" if kst_str else f"{reextracted}건 · {model_ver}"
                elif stage["id"] == "recluster":
                    stage["status"] = "done" if cache_warmed else "waiting"
                    stage["detail"] = f"완료 · {kst_str}" if cache_warmed and kst_str else "재추출 후 자동 실행"
    except Exception:
        pass

    return {
        "current_model": current_model,
        "training_data": training_data,
        "model_versions": model_versions,
        "config": {
            "min_quality": settings.ner_eval_min_quality,
            "min_samples": settings.ner_training_min_samples,
            "eval_sample_size": settings.ner_eval_sample_size,
        },
        "schedule": schedule,
        "pipeline": pipeline,
        "recent_evaluations": recent_evaluations,
        "predictions": predictions,
        "quality_analytics": quality_analytics,
        "finetune_status": finetune_status,
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

    # 각 쿼리를 독립 실행
    try:
        async with async_session_factory() as session:
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
    except Exception as e:
        logger.warning(f"stats overview query failed: {e}")

    try:
        async with async_session_factory() as session:
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
    except Exception as e:
        logger.warning(f"stats articles_by_date query failed: {e}")

    try:
        async with async_session_factory() as session:
            cat_col = Article.metadata_["category"].astext
            row = await session.execute(
                select(
                    cat_col.label("category"),
                    func.count(Article.id).label("count"),
                )
                .where(cat_col.isnot(None))
                .group_by(literal_column("category"))
                .order_by(func.count(Article.id).desc())
            )
            articles_by_category = [{"category": r.category, "count": r.count} for r in row.all()]
    except Exception as e:
        logger.warning(f"stats articles_by_category query failed: {e}")

    try:
        async with async_session_factory() as session:
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
    except Exception as e:
        logger.warning(f"stats top_publishers query failed: {e}")

    try:
        async with async_session_factory() as session:
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
        logger.warning(f"stats tracking_by_type query failed: {e}")

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
# Traffic — GeoIP helper
# ---------------------------------------------------------------------------

async def _resolve_geo_ips(ips: list[str]) -> dict[str, dict]:
    """IP 지리적 위치 일괄 조회 (ip-api.com + Redis 캐시, 24h TTL)"""
    if not ips:
        return {}

    results: dict[str, dict] = {}
    uncached: list[str] = []

    # Redis 캐시 확인
    try:
        from app.services.cache import cache_get, cache_set as _cache_set
        for ip in ips:
            cached = await cache_get(f"geo:{ip}")
            if cached:
                results[ip] = cached
            else:
                uncached.append(ip)
    except Exception:
        uncached = list(ips)

    if not uncached:
        return results

    # ip-api.com batch lookup (무료, 최대 100개)
    def _batch_lookup(ip_list: list[str]) -> list[dict]:
        import json
        import urllib.request
        req = urllib.request.Request(
            "http://ip-api.com/batch?fields=query,status,country,countryCode,city",
            data=json.dumps(ip_list[:100]).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    try:
        data = await asyncio.to_thread(_batch_lookup, uncached)
        from app.services.cache import cache_set as _cache_set
        for item in data:
            if item.get("status") == "success":
                geo = {
                    "country": item.get("country", "Unknown"),
                    "countryCode": item.get("countryCode", ""),
                    "city": item.get("city", ""),
                }
                results[item["query"]] = geo
                try:
                    await _cache_set(f"geo:{item['query']}", geo, ttl=86400)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"GeoIP batch lookup failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Traffic
# ---------------------------------------------------------------------------

@router.get("/traffic")
async def traffic(
    username: str = Depends(require_admin),
    period: str = Query("24h", regex="^(24h|7d|30d)$", description="Time period"),
):
    """HTTP 트래픽 대시보드 데이터"""
    from app.models.request_log import RequestLog

    now = datetime.now(timezone.utc)
    period_map = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    cutoff = now - period_map[period]

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # -- summary --
    summary: dict = {"today": 0, "week": 0, "month": 0, "avg_duration": 0.0, "error_rate": 0.0, "unique_ips": 0}
    try:
        async with async_session_factory() as session:
            row = await session.execute(
                select(
                    func.count(case((RequestLog.created_at >= today_start, RequestLog.id))).label("today"),
                    func.count(case((RequestLog.created_at >= week_start, RequestLog.id))).label("week"),
                    func.count(case((RequestLog.created_at >= month_start, RequestLog.id))).label("month"),
                    func.avg(case((RequestLog.created_at >= cutoff, RequestLog.duration_ms))).label("avg_duration"),
                    func.count(case((
                        (RequestLog.created_at >= cutoff) & (RequestLog.status_code >= 400),
                        RequestLog.id,
                    ))).label("errors"),
                    func.count(case((RequestLog.created_at >= cutoff, RequestLog.id))).label("period_total"),
                    func.count(func.distinct(case((RequestLog.created_at >= cutoff, RequestLog.client_ip)))).label("unique_ips"),
                )
            )
            r = row.one()
            period_total = r.period_total or 0
            errors = r.errors or 0
            summary = {
                "today": r.today or 0,
                "week": r.week or 0,
                "month": r.month or 0,
                "avg_duration": round(float(r.avg_duration), 1) if r.avg_duration else 0.0,
                "error_rate": round(errors / period_total * 100, 1) if period_total > 0 else 0.0,
                "unique_ips": r.unique_ips or 0,
            }
    except Exception as e:
        logger.warning(f"traffic summary query failed: {e}")

    # -- hourly (last 24h, KST) --
    hourly: list[dict] = []
    try:
        async with async_session_factory() as session:
            h24 = now - timedelta(hours=24)
            kst_col = func.timezone(literal_column("'Asia/Seoul'"), RequestLog.created_at)
            hour_trunc = func.date_trunc(literal_column("'hour'"), kst_col)
            rows = await session.execute(
                select(
                    hour_trunc.label("hour"),
                    func.count(RequestLog.id).label("count"),
                    func.avg(RequestLog.duration_ms).label("avg_duration"),
                ).where(
                    RequestLog.created_at >= h24
                ).group_by(
                    hour_trunc
                ).order_by(
                    hour_trunc
                )
            )
            hourly = [
                {
                    "hour": r.hour.isoformat() if r.hour else None,
                    "count": r.count,
                    "avg_duration": round(float(r.avg_duration), 1) if r.avg_duration else 0.0,
                }
                for r in rows.all()
            ]
    except Exception as e:
        logger.warning(f"traffic hourly query failed: {e}")

    # -- daily (last 30d, KST) --
    daily: list[dict] = []
    try:
        async with async_session_factory() as session:
            d30 = now - timedelta(days=30)
            kst_date = cast(func.timezone(literal_column("'Asia/Seoul'"), RequestLog.created_at), Date)
            rows = await session.execute(
                select(
                    kst_date.label("date"),
                    func.count(RequestLog.id).label("count"),
                    func.avg(RequestLog.duration_ms).label("avg_duration"),
                    func.count(case((RequestLog.status_code >= 400, RequestLog.id))).label("errors"),
                ).where(
                    RequestLog.created_at >= d30
                ).group_by(
                    kst_date
                ).order_by(
                    kst_date
                )
            )
            daily = [
                {
                    "date": r.date.isoformat(),
                    "count": r.count,
                    "avg_duration": round(float(r.avg_duration), 1) if r.avg_duration else 0.0,
                    "errors": r.errors or 0,
                }
                for r in rows.all()
            ]
    except Exception as e:
        logger.warning(f"traffic daily query failed: {e}")

    # -- status_distribution --
    status_distribution: list[dict] = []
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                select(
                    RequestLog.status_code,
                    func.count(RequestLog.id).label("count"),
                ).where(
                    RequestLog.created_at >= cutoff
                ).group_by(
                    RequestLog.status_code
                ).order_by(
                    func.count(RequestLog.id).desc()
                )
            )
            status_distribution = [
                {"status_code": r.status_code, "count": r.count}
                for r in rows.all()
            ]
    except Exception as e:
        logger.warning(f"traffic status_distribution query failed: {e}")

    # -- top_by_count --
    top_by_count: list[dict] = []
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                select(
                    RequestLog.method,
                    RequestLog.path,
                    func.count(RequestLog.id).label("count"),
                    func.avg(RequestLog.duration_ms).label("avg_duration"),
                ).where(
                    RequestLog.created_at >= cutoff
                ).group_by(
                    RequestLog.method, RequestLog.path
                ).order_by(
                    func.count(RequestLog.id).desc()
                ).limit(15)
            )
            top_by_count = [
                {
                    "method": r.method,
                    "path": r.path,
                    "count": r.count,
                    "avg_duration": round(float(r.avg_duration), 1) if r.avg_duration else 0.0,
                }
                for r in rows.all()
            ]
    except Exception as e:
        logger.warning(f"traffic top_by_count query failed: {e}")

    # -- top_by_duration --
    top_by_duration: list[dict] = []
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                select(
                    RequestLog.method,
                    RequestLog.path,
                    func.count(RequestLog.id).label("count"),
                    func.avg(RequestLog.duration_ms).label("avg_duration"),
                    func.max(RequestLog.duration_ms).label("max_duration"),
                ).where(
                    RequestLog.created_at >= cutoff
                ).group_by(
                    RequestLog.method, RequestLog.path
                ).order_by(
                    func.avg(RequestLog.duration_ms).desc()
                ).limit(15)
            )
            top_by_duration = [
                {
                    "method": r.method,
                    "path": r.path,
                    "count": r.count,
                    "avg_duration": round(float(r.avg_duration), 1) if r.avg_duration else 0.0,
                    "max_duration": round(float(r.max_duration), 1) if r.max_duration else 0.0,
                }
                for r in rows.all()
            ]
    except Exception as e:
        logger.warning(f"traffic top_by_duration query failed: {e}")

    # -- recent_errors --
    recent_errors: list[dict] = []
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                select(
                    RequestLog.method,
                    RequestLog.path,
                    RequestLog.status_code,
                    RequestLog.duration_ms,
                    RequestLog.client_ip,
                    RequestLog.created_at,
                ).where(
                    RequestLog.status_code >= 400,
                ).order_by(
                    RequestLog.created_at.desc()
                ).limit(30)
            )
            recent_errors = [
                {
                    "method": r.method,
                    "path": r.path,
                    "status_code": r.status_code,
                    "duration_ms": round(r.duration_ms, 1),
                    "client_ip": r.client_ip,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows.all()
            ]
    except Exception as e:
        logger.warning(f"traffic recent_errors query failed: {e}")

    # -- geo_distribution --
    geo_distribution: list[dict] = []
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                select(
                    RequestLog.client_ip,
                    func.count(RequestLog.id).label("count"),
                ).where(
                    RequestLog.created_at >= cutoff,
                    RequestLog.client_ip.isnot(None),
                ).group_by(RequestLog.client_ip)
            )
            ip_counts = {r.client_ip: r.count for r in rows.all()}

        if ip_counts:
            geo_map = await _resolve_geo_ips(list(ip_counts.keys()))
            country_agg: dict[str, dict] = {}
            for ip, count in ip_counts.items():
                geo = geo_map.get(ip, {"country": "Unknown", "countryCode": "", "city": ""})
                country = geo["country"]
                if country not in country_agg:
                    country_agg[country] = {
                        "country": country,
                        "countryCode": geo.get("countryCode", ""),
                        "count": 0,
                        "unique_ips": 0,
                        "cities": {},
                    }
                country_agg[country]["count"] += count
                country_agg[country]["unique_ips"] += 1
                city = geo.get("city", "")
                if city:
                    country_agg[country]["cities"][city] = country_agg[country]["cities"].get(city, 0) + count

            geo_distribution = sorted(country_agg.values(), key=lambda x: -x["count"])
            for entry in geo_distribution:
                entry["cities"] = sorted(
                    [{"city": c, "count": n} for c, n in entry["cities"].items()],
                    key=lambda x: -x["count"],
                )[:5]
    except Exception as e:
        logger.warning(f"traffic geo_distribution failed: {e}")

    return {
        "summary": summary,
        "hourly": hourly,
        "daily": daily,
        "status_distribution": status_distribution,
        "top_by_count": top_by_count,
        "top_by_duration": top_by_duration,
        "recent_errors": recent_errors,
        "geo_distribution": geo_distribution,
    }


# ---------------------------------------------------------------------------
# Settings (read-only, secrets masked)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@router.get("/reports")
async def reports_list(
    username: str = Depends(require_admin),
    report_type: str | None = Query(None, description="Filter: weekly, monthly, alert"),
    severity: str | None = Query(None, description="Filter: info, warning, critical"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """리포트 목록 조회 (게시판)"""
    try:
        async with async_session_factory() as session:
            stmt = select(AdminReport).order_by(AdminReport.created_at.desc())

            if report_type:
                stmt = stmt.where(AdminReport.report_type == report_type)
            if severity:
                stmt = stmt.where(AdminReport.severity == severity)

            # total count
            count_stmt = select(func.count(AdminReport.id))
            if report_type:
                count_stmt = count_stmt.where(AdminReport.report_type == report_type)
            if severity:
                count_stmt = count_stmt.where(AdminReport.severity == severity)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = stmt.offset(offset).limit(limit)
            rows = await session.execute(stmt)
            reports = rows.scalars().all()

            return {
                "reports": [
                    {
                        "id": str(r.id),
                        "report_type": r.report_type,
                        "title": r.title,
                        "summary": r.summary,
                        "category": r.category,
                        "severity": r.severity,
                        "email_sent": r.email_sent,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in reports
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
    except Exception as e:
        logger.warning(f"reports list query failed: {e}")
        return {"reports": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/reports/{report_id}")
async def report_detail(
    report_id: str,
    username: str = Depends(require_admin),
):
    """리포트 상세 조회"""
    try:
        import uuid as _uuid
        rid = _uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 리포트 ID 형식입니다")

    async with async_session_factory() as session:
        row = await session.execute(
            select(AdminReport).where(AdminReport.id == rid)
        )
        report = row.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")

        return {
            "id": str(report.id),
            "report_type": report.report_type,
            "title": report.title,
            "summary": report.summary,
            "content_json": report.content_json,
            "category": report.category,
            "severity": report.severity,
            "email_sent": report.email_sent,
            "email_sent_at": report.email_sent_at.isoformat() if report.email_sent_at else None,
            "email_error": report.email_error,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }


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
            "max_articles_per_run": MAX_ARTICLES_PER_RUN,
            "retention_days": settings.article_retention_days,
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
            "max_versions": settings.ner_max_model_versions,
        },
        "system": {
            "app_env": settings.app_env,
            "debug": settings.app_debug,
            "retention_days": settings.article_retention_days,
        },
    }
