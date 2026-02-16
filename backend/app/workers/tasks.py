"""
# tasks.py - Celery Async Tasks
# Version: 0.7.0
# Description: 기사 분석 파이프라인 + 백그라운드 크롤링
# Changes:
#   - 0.2.0: 기사 분석 파이프라인 (크롤링 → 임베딩 → 유사도 → 타임라인)
#   - 0.3.0: fetch_trending_news, cleanup_old_articles, 파이프라인 최적화
#   - 0.4.0: origin content null이면 파이프라인 시작 시 백그라운드 크롤링
#   - 0.5.0: 3단 카테고리 분류 + 기존 기사 카테고리 마이그레이션
#   - 0.6.0: 2단계 추적 - 즉시 추적(Qdrant only) + Live 추적(full pipeline)
#   - 0.7.0: 캐시 무효화 통합, distributed lock, run_async 헬퍼
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from celery.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """Celery 태스크에서 async 코루틴 실행을 위한 헬퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _create_worker_engine():
    """Celery 워커 전용 DB 엔진 생성 (이벤트 루프 충돌 방지)"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import get_settings

    settings = get_settings()
    worker_engine = create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        pool_size=2,
        max_overflow=1,
    )
    factory = async_sessionmaker(
        worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return worker_engine, factory


# ── Background Crawling Tasks ──


@celery_app.task(bind=True, soft_time_limit=1500, time_limit=1800)
def fetch_trending_news(self):
    """
    백그라운드 트렌딩 뉴스 크롤링 태스크

    카테고리 RSS 피드 수집 → DB 중복 체크 → 배치 크롤링 → 배치 임베딩 → 저장
    Celery Beat에 의해 30분마다 실행
    """
    from app.config import get_settings
    settings = get_settings()

    if not settings.background_crawl_enabled:
        logger.warning("Background crawling is disabled")
        return {"status": "disabled"}

    from app.services.cache import set_crawl_status, acquire_task_lock, release_task_lock

    # 동시실행 방지 (distributed lock)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        lock_acquired = loop.run_until_complete(
            acquire_task_lock("fetch_trending_news", timeout=1800)
        )
        if not lock_acquired:
            logger.warning("fetch_trending_news already running, skipping")
            return {"status": "skipped", "reason": "already_running"}

        logger.warning("fetch_trending_news started")
        result = loop.run_until_complete(_run_fetch_trending())
        logger.warning(f"fetch_trending_news completed: {result}")
        return result
    except SoftTimeLimitExceeded:
        logger.error("fetch_trending_news timed out")
        loop.run_until_complete(set_crawl_status("idle"))
        return {"status": "timeout"}
    except Exception as e:
        logger.error(f"fetch_trending_news failed: {e}", exc_info=True)
        loop.run_until_complete(set_crawl_status("idle"))
        return {"status": "error", "error": str(e)[:200]}
    finally:
        loop.run_until_complete(release_task_lock("fetch_trending_news"))
        loop.close()


async def _run_fetch_trending():
    """백그라운드 트렌딩 뉴스 수집 파이프라인"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.core.crawler import crawl_articles_batch
    from app.services.embedding import create_embeddings_batch, get_article_text
    from app.services.vector_store import upsert_embedding
    from app.services.news_feed import fetch_all_category_feeds, fetch_all_publisher_feeds
    from app.services.keyword_extractor import extract_keywords_batch
    from app.workers.beat_schedule import (
        CATEGORY_FEEDS, PUBLISHER_FEEDS, CRAWL_BATCH_SIZE, MAX_ARTICLES_PER_RUN,
        FEED_LIMIT_PER_CATEGORY, PUBLISHER_FEED_LIMIT,
    )

    from app.services.cache import set_crawl_status

    worker_engine, session_factory = _create_worker_engine()
    try:
        # 1. 카테고리 피드 수집 (Google News)
        await set_crawl_status("fetching", "RSS 피드 수집중")
        feed_articles = await fetch_all_category_feeds(
            CATEGORY_FEEDS,
            limit_per_category=FEED_LIMIT_PER_CATEGORY,
            max_total=MAX_ARTICLES_PER_RUN,
        )

        # 1-2. 한국 언론사 RSS 피드 수집
        google_urls = {a["url"] for a in feed_articles}
        await set_crawl_status("fetching", "언론사 RSS 수집중")
        publisher_articles = await fetch_all_publisher_feeds(
            PUBLISHER_FEEDS,
            limit_per_publisher=PUBLISHER_FEED_LIMIT,
            max_total=60,
            exclude_urls=google_urls,
        )
        feed_articles.extend(publisher_articles)

        if not feed_articles:
            logger.warning("No articles from feeds — check RSS feed URLs")
            await set_crawl_status("idle")
            return {"status": "ok", "fetched": 0, "crawled": 0, "embedded": 0}

        feed_urls = [a["url"] for a in feed_articles]

        # 2. DB에서 이미 존재하는 URL 확인
        # Google News URL과 실제 URL이 다를 수 있으므로, 피드 URL + 최근 기사 URL 모두 체크
        async with session_factory() as db:
            result = await db.execute(
                select(Article.url, Article.qdrant_point_id).where(
                    Article.url.in_(feed_urls)
                )
            )
            existing = {row.url: row.qdrant_point_id for row in result.all()}

        urls_to_crawl = [u for u in feed_urls if u not in existing]
        logger.warning(
            f"Feed articles: {len(feed_urls)}, "
            f"already in DB: {len(existing)}, "
            f"to crawl: {len(urls_to_crawl)}"
        )

        if not urls_to_crawl:
            await set_crawl_status("idle")
            return {"status": "ok", "fetched": len(feed_urls), "crawled": 0, "embedded": 0}

        # 3. 미크롤링 기사 배치 크롤링
        await set_crawl_status("crawling", f"{len(urls_to_crawl[:CRAWL_BATCH_SIZE])}건 크롤링중")
        crawled = await crawl_articles_batch(urls_to_crawl[:CRAWL_BATCH_SIZE])
        logger.warning(f"Crawled {len(crawled)} / {len(urls_to_crawl)} articles")

        if not crawled:
            logger.warning("No articles successfully crawled")
            await set_crawl_status("idle")
            return {"status": "ok", "fetched": len(feed_urls), "crawled": 0, "embedded": 0}

        # 3.5. NER 키워드 추출
        await set_crawl_status("extracting", f"{len(crawled)}건 키워드 추출중")
        crawled_titles = [a.get("title", "") for a in crawled]
        keywords_batch = extract_keywords_batch(crawled_titles)
        for article_data, kw_data in zip(crawled, keywords_batch):
            meta = article_data.get("metadata_", {}) or {}
            meta["keywords_data"] = kw_data
            article_data["metadata_"] = meta
        logger.info(f"Extracted keywords for {len(crawled)} articles")

        # 4. DB 저장 + 임베딩 생성
        articles_to_embed = []
        new_articles_count = 0
        async with session_factory() as db:
            # feed_category 매핑 (피드 URL → category, 크롤러가 URL을 변환하므로 양쪽 매핑)
            url_category_map = {
                a["url"]: a.get("feed_category")
                for a in feed_articles if "feed_category" in a
            }

            from app.services.category import resolve_category

            for article_data in crawled:
                # 크롤러가 URL을 변환한 경우 원본 URL로 카테고리 매핑
                original_url = article_data.pop("_original_url", article_data["url"])
                actual_url = article_data["url"]
                source_category = article_data.pop("source_category", None)
                # DB upsert (실제 URL 기준)
                result = await db.execute(
                    select(Article).where(Article.url == actual_url)
                )
                article = result.scalar_one_or_none()
                if not article:
                    # feed_category: 원본 URL → 실제 URL 순서로 매핑
                    feed_cat = url_category_map.get(original_url) or url_category_map.get(actual_url)
                    meta = article_data.get("metadata_", {}) or {}
                    if feed_cat:
                        meta["feed_category"] = feed_cat
                    # 3단 카테고리 해결: source(HTML) → feed(RSS) → keyword(제목)
                    resolved = resolve_category(
                        source_category=source_category,
                        feed_category=feed_cat,
                        title=article_data.get("title"),
                    )
                    if resolved:
                        meta["category"] = resolved
                    if source_category:
                        meta["source_category"] = source_category
                    article_data["metadata_"] = meta
                    article = Article(**article_data)
                    db.add(article)
                    await db.flush()
                    new_articles_count += 1

                # 임베딩이 없는 기사만 수집
                if not article.qdrant_point_id:
                    articles_to_embed.append(article)

            logger.warning(f"New articles saved: {new_articles_count}, duplicates skipped: {len(crawled) - new_articles_count}")

            await db.commit()

            # 5. 배치 임베딩 생성 + Qdrant 저장
            if articles_to_embed:
                await set_crawl_status("embedding", f"{len(articles_to_embed)}건 임베딩 생성중")
                texts = [
                    get_article_text(a.title, a.content)
                    for a in articles_to_embed
                ]
                embeddings = create_embeddings_batch(texts)

                embedded_count = 0
                for article, embedding in zip(articles_to_embed, embeddings):
                    if embedding is None:
                        logger.warning(f"Skipping article {article.id}: embedding generation failed")
                        continue
                    article_meta = article.metadata_ or {}
                    kw_data = article_meta.get("keywords_data", {})
                    payload = {
                        "title": article.title,
                        "publisher": article.publisher,
                        "published_at": str(article.published_at) if article.published_at else None,
                        "keywords": kw_data.get("keywords", []),
                    }
                    point_id = upsert_embedding(str(article.id), embedding, payload)
                    article.qdrant_point_id = point_id
                    embedded_count += 1

                await db.commit()
                logger.info(f"Embedded {embedded_count}/{len(articles_to_embed)} articles")

            # 5.5. 샘플링 품질 평가 (비용 절감)
            try:
                from app.services.evaluator import evaluate_batch_sample
                eval_articles = [
                    {"title": a.title, "keywords_data": (a.metadata_ or {}).get("keywords_data", {})}
                    for a in articles_to_embed[:20]
                ]
                evaluate_batch_sample(eval_articles, sample_size=5)
            except Exception as e:
                logger.warning(f"Sampling evaluation skipped: {e}")

        # 6. 상태 초기화 + 캐시 무효화 + SSE 이벤트 발행
        await set_crawl_status("idle")
        from app.services.cache import invalidate_all_trend_caches, publish_event
        await invalidate_all_trend_caches()
        await publish_event("stats_updated", {
            "type": "crawl_complete",
            "crawled": len(crawled),
            "embedded": len(articles_to_embed),
        })

        return {
            "status": "ok",
            "fetched": len(feed_urls),
            "crawled": len(crawled),
            "embedded": len(articles_to_embed),
            "from_publishers": len(publisher_articles),
        }

    finally:
        await worker_engine.dispose()


@celery_app.task(bind=True, soft_time_limit=300, time_limit=360)
def cleanup_old_articles(self):
    """
    오래된 기사 정리 태스크

    article_retention_days 초과 기사 삭제 (timeline_entries에서 참조되는 기사는 보존)
    Celery Beat에 의해 매일 03:00에 실행
    """
    try:
        return run_async(_run_cleanup())
    except Exception as e:
        logger.error(f"cleanup_old_articles failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


async def _run_cleanup():
    """오래된 기사 삭제 파이프라인"""
    from sqlalchemy import select, delete, func
    from app.models.article import Article
    from app.models.timeline import TimelineEntry
    from app.models.search_log import SearchLog
    from app.services.vector_store import get_qdrant_client
    from app.config import get_settings

    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.article_retention_days)

    worker_engine, session_factory = _create_worker_engine()
    try:
        async with session_factory() as db:
            # timeline_entries에서 참조되는 article_id 목록
            referenced_result = await db.execute(
                select(TimelineEntry.article_id).distinct()
            )
            referenced_ids = {row[0] for row in referenced_result.all()}

            # 삭제 대상: retention 초과 + timeline에서 참조되지 않는 기사
            old_articles_result = await db.execute(
                select(Article.id, Article.qdrant_point_id).where(
                    Article.created_at < cutoff
                )
            )
            old_articles = old_articles_result.all()

            to_delete_ids = []
            qdrant_point_ids = []
            for row in old_articles:
                if row.id not in referenced_ids:
                    to_delete_ids.append(row.id)
                    if row.qdrant_point_id:
                        qdrant_point_ids.append(str(row.qdrant_point_id))

            # search_logs 정리 (90일 초과 로그 삭제)
            old_logs_result = await db.execute(
                delete(SearchLog).where(SearchLog.created_at < cutoff)
            )
            deleted_logs = old_logs_result.rowcount
            logger.info(f"Deleted {deleted_logs} old search logs")

            if not to_delete_ids:
                logger.info("No old articles to clean up")
                return {"status": "ok", "deleted": 0, "deleted_logs": deleted_logs}

            # Qdrant 포인트 삭제
            if qdrant_point_ids:
                try:
                    client = get_qdrant_client()
                    client.delete(
                        collection_name=settings.qdrant_collection,
                        points_selector=qdrant_point_ids,
                    )
                    logger.info(f"Deleted {len(qdrant_point_ids)} Qdrant points")
                except Exception as e:
                    logger.warning(f"Failed to delete Qdrant points: {e}")

            # DB 기사 삭제
            await db.execute(
                delete(Article).where(Article.id.in_(to_delete_ids))
            )
            await db.commit()

            logger.info(f"Cleaned up {len(to_delete_ids)} old articles")
            return {"status": "ok", "deleted": len(to_delete_ids), "deleted_logs": deleted_logs}

    finally:
        await worker_engine.dispose()


# ── Instant Tracking Task (Qdrant-only) ──


@celery_app.task(bind=True, max_retries=2, soft_time_limit=120, time_limit=150)
def analyze_article_instant(self, tracking_id: str, article_id: str):
    """
    즉시 추적 파이프라인 (Celery 태스크)

    기존 DB/Qdrant 데이터에서만 검색하여 빠른 결과 제공 (크롤링 없음)
    실행 순서:
    1. 원본 기사 임베딩 생성 (없으면)
    2. Qdrant 벡터 검색으로 유사 기사 탐색
    3. 타임라인 구성
    4. DB 저장

    Timeouts:
    - soft_time_limit=120 (2분): 크롤링 없이 빠르게 완료
    - time_limit=150 (2.5분): 강제 종료
    """
    try:
        run_async(_run_instant_pipeline(self, tracking_id, article_id))
    except SoftTimeLimitExceeded:
        logger.error(f"Instant task timed out: tracking_id={tracking_id}")
        run_async(_mark_failed(tracking_id, "즉시 분석 시간이 초과되었습니다."))


async def _run_instant_pipeline(task, tracking_id: str, article_id: str):
    """즉시 추적 파이프라인 - Qdrant 벡터 검색만 수행"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.models.timeline import TrackingRequest, TimelineEntry
    from app.core.analyzer import analyze_article, find_similar_articles
    from app.core.timeline import build_timeline
    from app.services.embedding import create_embedding, get_article_text
    from app.services.keyword_extractor import extract_keywords

    worker_engine, session_factory = _create_worker_engine()
    tracking = None
    try:
        async with session_factory() as db:
            # 추적 상태 업데이트
            result = await db.execute(
                select(TrackingRequest).where(TrackingRequest.id == tracking_id)
            )
            tracking = result.scalar_one()
            tracking.status = "processing"
            tracking.progress = 10
            await db.commit()

            # 1. 원본 기사 로드
            result = await db.execute(
                select(Article).where(Article.id == article_id)
            )
            origin = result.scalar_one()

            # 2. 원본 기사 NER 키워드 추출 (없으면)
            origin_meta = dict(origin.metadata_ or {})
            if "keywords_data" not in origin_meta:
                kw_data = extract_keywords(origin.title)
                origin_meta["keywords_data"] = kw_data
                origin.metadata_ = origin_meta
                await db.commit()

            tracking.progress = 20
            await db.commit()

            # 3. 원본 기사 임베딩 생성 (없으면)
            origin_kw = origin_meta.get("keywords_data", {})
            if origin.qdrant_point_id:
                # 이미 임베딩이 있으면 텍스트에서 재생성 (검색용)
                text = get_article_text(origin.title, origin.content)
                origin_embedding = create_embedding(text)
            else:
                point_id, origin_embedding = analyze_article(
                    article_id=str(origin.id),
                    title=origin.title,
                    content=origin.content,
                    publisher=origin.publisher,
                    published_at=str(origin.published_at) if origin.published_at else None,
                    keywords=origin_kw.get("keywords", []),
                )
                origin.qdrant_point_id = point_id

            tracking.progress = 40
            await db.commit()

            # 4. Qdrant에서 유사 기사 검색 (기존 데이터만)
            qdrant_results = find_similar_articles(
                origin_embedding,
                exclude_article_id=str(origin.id),
            )

            tracking.progress = 60
            tracking.total_articles = len(qdrant_results)
            await db.commit()

            # 5. 유사 기사 정보 로드 (DB에서)
            similar_articles = []
            article_ids = [r["payload"].get("article_id") for r in qdrant_results if r["payload"].get("article_id")]
            if article_ids:
                result = await db.execute(
                    select(Article).where(Article.id.in_(article_ids))
                )
                db_articles = {str(a.id): a for a in result.scalars().all()}

                for qr in qdrant_results:
                    aid = qr["payload"].get("article_id")
                    if aid and aid in db_articles:
                        article = db_articles[aid]
                        similar_articles.append({
                            "id": aid,
                            "title": article.title,
                            "published_at": article.published_at,
                            "publisher": article.publisher,
                            "score": qr["score"],
                            "category": qr["category"],
                            "embedding": None,
                        })

            tracking.progress = 80
            await db.commit()

            # 6. 타임라인 구성
            input_data = {
                "id": str(origin.id),
                "title": origin.title,
                "published_at": origin.published_at,
            }
            timeline_entries, true_origin_id = build_timeline(input_data, similar_articles)

            # origin_article_id 업데이트
            if str(tracking.origin_article_id) != true_origin_id:
                import uuid as _uuid
                tracking.origin_article_id = _uuid.UUID(true_origin_id)

            # 7. 타임라인 엔트리 DB 저장
            seen_article_ids = set()
            for entry_data in timeline_entries:
                aid = entry_data["article_id"]
                if aid in seen_article_ids:
                    continue
                seen_article_ids.add(aid)
                entry = TimelineEntry(
                    tracking_id=tracking_id,
                    **entry_data,
                )
                db.add(entry)

            tracking.status = "completed"
            tracking.progress = 100
            tracking.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # 캐시 무효화 + 이벤트 발행
            from app.services.cache import publish_event
            await publish_event("stats_updated", {
                "type": "tracking_complete",
                "tracking_id": tracking_id,
                "tracking_type": "instant",
                "articles": len(similar_articles),
            })

            logger.info(
                f"Instant pipeline completed: tracking_id={tracking_id}, "
                f"articles={len(similar_articles)}"
            )

    except SoftTimeLimitExceeded:
        raise

    except Exception as e:
        logger.error(f"Instant pipeline failed: tracking_id={tracking_id}, error={e}", exc_info=True)
        if tracking is not None:
            try:
                async with session_factory() as db:
                    result = await db.execute(
                        select(TrackingRequest).where(TrackingRequest.id == tracking_id)
                    )
                    t = result.scalar_one_or_none()
                    if t:
                        t.status = "error"
                        t.error_message = str(e)[:500]
                        await db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {inner_e}")
        raise

    finally:
        await worker_engine.dispose()


# ── Article Propagation Analysis Task (Live Tracking) ──


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, time_limit=660)
def analyze_article_propagation(self, tracking_id: str, article_id: str):
    """
    기사 전파 분석 파이프라인 (Celery 태스크)

    [BUSINESS LOGIC - DO NOT MODIFY]
    실행 순서:
    1. 원본 기사 임베딩 생성 → Qdrant 저장
    2. 키워드 추출 → 유사 기사 검색
    3. 유사 기사 크롤링 → 임베딩 → Qdrant 저장
    4. 유사도 매트릭스 계산
    5. 타임라인 구성 (시간순 + 전파 추론)
    6. DB 저장

    Timeouts:
    - soft_time_limit=600 (10분): SoftTimeLimitExceeded 발생, 정리 가능
    - time_limit=660 (11분): 강제 종료
    """
    try:
        run_async(_run_pipeline(self, tracking_id, article_id))
    except SoftTimeLimitExceeded:
        logger.error(f"Task timed out: tracking_id={tracking_id}")
        run_async(_mark_failed(tracking_id, "분석 시간이 초과되었습니다. (10분 제한)"))


async def _mark_failed(tracking_id: str, error_message: str):
    """태스크 실패 상태로 업데이트"""
    from sqlalchemy import select
    from app.models.timeline import TrackingRequest

    worker_engine, session_factory = _create_worker_engine()
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(TrackingRequest).where(TrackingRequest.id == tracking_id)
            )
            tracking = result.scalar_one_or_none()
            if tracking:
                tracking.status = "error"
                tracking.error_message = error_message[:500]
                await db.commit()
    except Exception as e:
        logger.error(f"Failed to mark tracking as failed: {e}")
    finally:
        await worker_engine.dispose()


async def _run_pipeline(task, tracking_id: str, article_id: str):
    """비동기 분석 파이프라인 실행 (pre-crawled 기사 활용 최적화)"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.models.timeline import TrackingRequest, TimelineEntry
    from app.core.crawler import crawl_article, crawl_articles_batch
    from app.core.analyzer import analyze_article, find_similar_articles
    from app.core.timeline import build_timeline
    from app.services.news_search import search_news
    from app.services.embedding import create_embeddings_batch, get_article_text
    from app.services.vector_store import upsert_embedding
    from app.services.keyword_extractor import extract_keywords

    worker_engine, session_factory = _create_worker_engine()
    tracking = None
    try:
        async with session_factory() as db:
            # 추적 상태 업데이트
            result = await db.execute(
                select(TrackingRequest).where(TrackingRequest.id == tracking_id)
            )
            tracking = result.scalar_one()
            tracking.status = "processing"
            tracking.progress = 10
            await db.commit()

            # 1. 원본 기사 로드
            result = await db.execute(
                select(Article).where(Article.id == article_id)
            )
            origin = result.scalar_one()

            # 1-1. content가 없으면 백그라운드 크롤링으로 보완
            if not origin.content:
                logger.info(f"Origin article has no content, crawling: {origin.url[:80]}")
                try:
                    crawled_data = await crawl_article(origin.url)
                    if crawled_data and crawled_data.get("content"):
                        origin.content = crawled_data["content"]
                        if not origin.summary and crawled_data.get("summary"):
                            origin.summary = crawled_data["summary"]
                        if not origin.author and crawled_data.get("author"):
                            origin.author = crawled_data["author"]
                        await db.commit()
                        logger.info("Origin article content filled via background crawl")
                except Exception as e:
                    logger.warning(f"Background crawl for origin failed (continuing): {e}")

            # 1.5. 원본 기사 NER 키워드 추출
            origin_meta = dict(origin.metadata_ or {})
            if "keywords_data" not in origin_meta:
                kw_data = extract_keywords(origin.title)
                origin_meta["keywords_data"] = kw_data
                origin.metadata_ = origin_meta
                await db.commit()

            # 2. 원본 기사 임베딩 생성 (NER 키워드 포함)
            origin_kw = origin_meta.get("keywords_data", {})
            point_id, origin_embedding = analyze_article(
                article_id=str(origin.id),
                title=origin.title,
                content=origin.content,
                publisher=origin.publisher,
                published_at=str(origin.published_at) if origin.published_at else None,
                keywords=origin_kw.get("keywords", []),
            )
            origin.qdrant_point_id = point_id
            tracking.progress = 20
            await db.commit()

            # 3. 유사 기사 검색 (키워드 기반)
            search_results = await search_news(origin.title, limit=30)
            tracking.progress = 40
            tracking.total_articles = len(search_results)
            await db.commit()

            # 4. Pre-crawled 기사 활용 최적화
            urls = [r["url"] for r in search_results if r["url"] != origin.url]
            urls = urls[:20]

            # DB에서 이미 크롤링된 기사 조회
            existing_result = await db.execute(
                select(Article).where(Article.url.in_(urls))
            )
            existing_articles = {a.url: a for a in existing_result.scalars().all()}

            # 미크롤링 URL만 크롤링
            urls_to_crawl = [u for u in urls if u not in existing_articles]
            logger.info(
                f"Pre-crawled: {len(existing_articles)}, "
                f"to crawl: {len(urls_to_crawl)}"
            )

            crawled = await crawl_articles_batch(urls_to_crawl) if urls_to_crawl else []
            tracking.progress = 60
            await db.commit()

            # 5. 크롤링된 기사 DB 저장 + 배치 임베딩
            similar_articles = []
            seen_ids = {str(origin.id)}
            articles_needing_embed = []

            # 기존 DB 기사 처리
            for url, article in existing_articles.items():
                aid = str(article.id)
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)
                similar_articles.append({
                    "id": aid,
                    "title": article.title,
                    "published_at": article.published_at,
                    "publisher": article.publisher,
                    "embedding": None,
                })
                if not article.qdrant_point_id:
                    articles_needing_embed.append(article)

            # 새로 크롤링된 기사 처리
            valid_columns = {c.key for c in Article.__table__.columns}
            for article_data in crawled:
                # 크롤러 내부 필드 제거 (_original_url, source_category 등)
                filtered = {k: v for k, v in article_data.items() if k in valid_columns}
                result = await db.execute(
                    select(Article).where(Article.url == filtered["url"])
                )
                article = result.scalar_one_or_none()
                if not article:
                    article = Article(**filtered)
                    db.add(article)
                    await db.flush()

                aid = str(article.id)
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)

                similar_articles.append({
                    "id": aid,
                    "title": article.title,
                    "published_at": article.published_at,
                    "publisher": article.publisher,
                    "embedding": None,
                })
                if not article.qdrant_point_id:
                    articles_needing_embed.append(article)

            # 배치 임베딩 (임베딩 없는 기사만) + NER 키워드 추출
            if articles_needing_embed:
                # NER 키워드 추출 (아직 없는 기사만)
                for a in articles_needing_embed:
                    a_meta = dict(a.metadata_ or {})
                    if "keywords_data" not in a_meta:
                        kw_data = extract_keywords(a.title)
                        a_meta["keywords_data"] = kw_data
                        a.metadata_ = a_meta

                texts = [
                    get_article_text(a.title, a.content)
                    for a in articles_needing_embed
                ]
                embeddings = create_embeddings_batch(texts)
                embed_map = {}
                for article, embedding in zip(articles_needing_embed, embeddings):
                    if embedding is None:
                        logger.warning(f"Skipping article {article.id}: embedding generation failed")
                        continue
                    article_meta = article.metadata_ or {}
                    kw_data = article_meta.get("keywords_data", {})
                    payload = {
                        "title": article.title,
                        "publisher": article.publisher,
                        "published_at": str(article.published_at) if article.published_at else None,
                        "keywords": kw_data.get("keywords", []),
                    }
                    pt_id = upsert_embedding(str(article.id), embedding, payload)
                    article.qdrant_point_id = pt_id
                    embed_map[str(article.id)] = embedding

                # similar_articles에 임베딩 매핑
                for sa in similar_articles:
                    if sa["id"] in embed_map:
                        sa["embedding"] = embed_map[sa["id"]]

                logger.info(f"Batch embedded {len(articles_needing_embed)} articles")

            tracking.progress = 75
            await db.commit()

            # 6. Qdrant에서 유사도 검색
            qdrant_results = find_similar_articles(
                origin_embedding,
                exclude_article_id=str(origin.id),
            )

            # 유사도 정보를 similar_articles에 매핑
            score_map = {r["payload"]["article_id"]: r for r in qdrant_results}
            for sa in similar_articles:
                if sa["id"] in score_map:
                    sa["score"] = score_map[sa["id"]]["score"]
                    sa["category"] = score_map[sa["id"]]["category"]
                else:
                    sa["score"] = 0.0
                    sa["category"] = "isolated"

            tracking.progress = 85
            await db.commit()

            # 7. 타임라인 구성 + 진짜 기원점 탐지
            input_data = {
                "id": str(origin.id),
                "title": origin.title,
                "published_at": origin.published_at,
            }
            timeline_entries, true_origin_id = build_timeline(input_data, similar_articles)

            # origin_article_id 업데이트 (진짜 기원이 입력 기사와 다를 경우)
            if str(tracking.origin_article_id) != true_origin_id:
                import uuid as _uuid
                tracking.origin_article_id = _uuid.UUID(true_origin_id)

            # 8. 타임라인 엔트리 DB 저장 (article_id 중복 제거)
            seen_article_ids = set()
            for entry_data in timeline_entries:
                aid = entry_data["article_id"]
                if aid in seen_article_ids:
                    continue
                seen_article_ids.add(aid)
                entry = TimelineEntry(
                    tracking_id=tracking_id,
                    **entry_data,
                )
                db.add(entry)

            tracking.status = "completed"
            tracking.progress = 100
            tracking.completed_at = datetime.now(timezone.utc)

            # Invalidate trend caches + notify frontend
            from app.services.cache import invalidate_all_trend_caches, publish_event
            await invalidate_all_trend_caches()
            await publish_event("stats_updated", {
                "type": "tracking_complete",
                "tracking_id": tracking_id,
                "tracking_type": "live",
                "articles": len(similar_articles),
            })

            await db.commit()
            logger.info(f"Live pipeline completed: tracking_id={tracking_id}, articles={len(similar_articles)}")

    except SoftTimeLimitExceeded:
        raise  # Let the outer handler deal with it

    except Exception as e:
        logger.error(f"Pipeline failed: tracking_id={tracking_id}, error={e}", exc_info=True)
        if tracking is not None:
            try:
                async with session_factory() as db:
                    result = await db.execute(
                        select(TrackingRequest).where(TrackingRequest.id == tracking_id)
                    )
                    t = result.scalar_one_or_none()
                    if t:
                        t.status = "error"
                        t.error_message = str(e)[:500]
                        await db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {inner_e}")
        raise

    finally:
        await worker_engine.dispose()


# ── Category Migration Task ──


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def migrate_article_categories(self):
    """
    기존 기사 카테고리 마이그레이션 (1회성)

    metadata["category"]가 없는 기사에 대해:
    1순위: feed_category (headlines 제외)
    2순위: 제목 키워드 매칭
    3순위: feed_category (headlines 포함)
    """
    try:
        result = run_async(_run_category_migration())
        logger.warning(f"Category migration completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Category migration failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=1860)
def reembed_all_articles(self):
    """
    전체 기사 임베딩 재생성 (1회성 마이그레이션)

    get_article_text() 변경 후 기존 기사 임베딩을 새 방식으로 재생성
    - 제목 3x 가중치 적용
    - 본문 윈도우 500→300자 축소
    - Qdrant 벡터 in-place 업데이트
    """
    try:
        result = run_async(_run_reembed_all())
        logger.warning(f"Re-embedding completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Re-embedding failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


async def _run_reembed_all():
    """전체 기사 NER 키워드 추출 + 임베딩 재생성 파이프라인"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.services.embedding import create_embeddings_batch, get_article_text
    from app.services.keyword_extractor import extract_keywords
    from app.services.vector_store import get_qdrant_client
    from app.config import get_settings
    from qdrant_client import models

    settings = get_settings()
    worker_engine, session_factory = _create_worker_engine()
    BATCH = 16  # Azure API 배치 크기에 맞춤

    try:
        async with session_factory() as db:
            # 모든 기사 대상 (NER 재추출 + 임베딩 재생성)
            result = await db.execute(select(Article))
            articles = result.scalars().all()

            if not articles:
                return {"status": "ok", "reembedded": 0}

            client = get_qdrant_client()
            total = len(articles)
            updated = 0

            for i in range(0, total, BATCH):
                batch = articles[i:i + BATCH]

                # NER 키워드 추출 + 메타데이터 업데이트
                for article in batch:
                    meta = dict(article.metadata_ or {})
                    kw_data = extract_keywords(article.title)
                    meta["keywords_data"] = kw_data
                    article.metadata_ = meta

                texts = [get_article_text(a.title, a.content) for a in batch]
                embeddings = create_embeddings_batch(texts)

                points = []
                for article, embedding in zip(batch, embeddings):
                    if embedding is None:
                        logger.warning(f"Skipping re-embed for article {article.id}: embedding failed")
                        continue
                    article_meta = article.metadata_ or {}
                    kw_data = article_meta.get("keywords_data", {})
                    point_id = str(article.qdrant_point_id) if article.qdrant_point_id else str(uuid.uuid4())
                    points.append(models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "article_id": str(article.id),
                            "title": article.title,
                            "publisher": article.publisher,
                            "published_at": str(article.published_at) if article.published_at else None,
                            "keywords": kw_data.get("keywords", []),
                        },
                    ))
                    # qdrant_point_id가 없었던 기사에 할당
                    if not article.qdrant_point_id:
                        article.qdrant_point_id = point_id

                client.upsert(
                    collection_name=settings.qdrant_collection,
                    points=points,
                )
                await db.commit()
                updated += len(batch)
                logger.info(f"Re-embedded {updated}/{total} articles")

            # 캐시 무효화
            from app.services.cache import invalidate_all_trend_caches
            await invalidate_all_trend_caches()

            return {"status": "ok", "reembedded": updated, "total": total}

    finally:
        await worker_engine.dispose()


async def _run_category_migration():
    """기존 기사 카테고리 일괄 분류"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.services.category import resolve_category

    worker_engine, session_factory = _create_worker_engine()
    try:
        async with session_factory() as db:
            # category가 없는 기사 전체 조회
            result = await db.execute(select(Article).limit(5000))
            articles = [
                a for a in result.scalars().all()
                if not (a.metadata_ or {}).get("category")
            ]

            if not articles:
                return {"status": "ok", "migrated": 0, "message": "No articles to migrate"}

            migrated = 0
            for article in articles:
                meta = dict(article.metadata_ or {})
                feed_cat = meta.get("feed_category")
                resolved = resolve_category(
                    source_category=None,
                    feed_category=feed_cat,
                    title=article.title,
                )

                if resolved:
                    meta["category"] = resolved
                    article.metadata_ = meta
                    migrated += 1

            await db.commit()
            logger.info(f"Migrated {migrated} / {len(articles)} articles")

            # 캐시 무효화
            from app.services.cache import invalidate_all_trend_caches
            await invalidate_all_trend_caches()

            return {"status": "ok", "migrated": migrated, "total": len(articles)}

    finally:
        await worker_engine.dispose()
