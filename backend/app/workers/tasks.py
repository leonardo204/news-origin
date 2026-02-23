"""
# tasks.py - Celery Async Tasks
# Version: 0.10.0
# Description: 기사 분석 파이프라인 + 백그라운드 크롤링
# Changes:
#   - 0.2.0: 기사 분석 파이프라인 (크롤링 → 임베딩 → 유사도 → 타임라인)
#   - 0.3.0: fetch_trending_news, cleanup_old_articles, 파이프라인 최적화
#   - 0.4.0: origin content null이면 파이프라인 시작 시 백그라운드 크롤링
#   - 0.5.0: 3단 카테고리 분류 + 기존 기사 카테고리 마이그레이션
#   - 0.6.0: 2단계 추적 - 즉시 추적(Qdrant only) + Live 추적(full pipeline)
#   - 0.7.0: 캐시 무효화 통합, distributed lock, run_async 헬퍼
#   - 0.8.0: 임베딩 실패 기사 DB 미저장 정책 - 임베딩 없는 기사는 검색/클러스터링 불가하므로 저장하지 않음
#   - 0.9.0: 임베딩 실패 재시도 큐, 워커 메모리 모니터링, 캐시 워밍 폴백 강화
#   - 0.10.0: trigger_bert_finetune Docker SDK 전환 — 별도 컨테이너 detach 실행, 워커 블로킹 제거
"""

import asyncio
import json
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

    from app.services.cache import set_crawl_status, acquire_task_lock, release_task_lock, _reset_redis

    # 동시실행 방지 (distributed lock)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    lock_acquired = False
    try:
        # 이전 이벤트 루프의 stale Redis 연결 제거 (재연결 실패 방지)
        _reset_redis()

        lock_acquired = loop.run_until_complete(
            acquire_task_lock("fetch_trending_news", timeout=1800)
        )
        if not lock_acquired:
            logger.warning("fetch_trending_news already running, skipping")
            return {"status": "skipped", "reason": "already_running"}

        logger.warning("fetch_trending_news started")
        result = loop.run_until_complete(_run_fetch_trending())
        logger.warning(f"fetch_trending_news completed: {result}")
        try:
            from app.services.webhook import send_webhook
            crawled_count = result.get("crawled", 0)
            embedded_count = result.get("embedded", 0)
            failed_count = crawled_count - embedded_count if crawled_count > embedded_count else 0
            send_webhook(
                title="크롤링 완료",
                description=f"{crawled_count}건 수집, {failed_count}건 임베딩 실패",
                color=0x2ECC71,
            )
        except Exception as _we:
            logger.warning(f"Webhook call failed (non-critical): {_we}")
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
        if lock_acquired:
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
            # RSS summary 매핑 (publisher RSS description → 크롤링 실패 시 폴백)
            url_rss_summary_map = {
                a["url"]: a["rss_summary"]
                for a in feed_articles if a.get("rss_summary")
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

                    # RSS summary 폴백: 크롤링 summary가 없을 때만 RSS description 사용
                    rss_summary = url_rss_summary_map.get(original_url) or url_rss_summary_map.get(actual_url)
                    if not article.summary and rss_summary:
                        article.summary = rss_summary

                # 임베딩이 없는 기사만 수집
                if not article.qdrant_point_id:
                    articles_to_embed.append(article)

            logger.warning(f"New articles saved: {new_articles_count}, duplicates skipped: {len(crawled) - new_articles_count}")

            await db.commit()

            # 5. 배치 임베딩 생성 + Qdrant 저장
            # [정책] 임베딩 실패 기사는 DB에서 삭제 — 임베딩 없는 기사는
            # 벡터 검색/클러스터링이 불가하여 서비스에서 활용할 수 없음
            embedded_count = 0
            if articles_to_embed:
                await set_crawl_status("embedding", f"{len(articles_to_embed)}건 임베딩 생성중")
                texts = [
                    get_article_text(a.title)
                    for a in articles_to_embed
                ]
                embeddings = create_embeddings_batch(texts)

                embedded_count = 0
                failed_articles = []
                for article, embedding in zip(articles_to_embed, embeddings):
                    if embedding is None:
                        logger.warning(f"Embedding failed, will delete article {article.id}: {article.title[:50]}")
                        failed_articles.append(article)
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

                # 임베딩 실패 기사 DB에서 삭제 + 재시도 큐에 추가
                from app.services.cache import get_redis
                redis_client = await get_redis()
                for article in failed_articles:
                    await db.delete(article)
                    # 재시도 큐에 기사 정보 저장 (최대 3회 재시도)
                    if redis_client:
                        import json as _json
                        retry_payload = _json.dumps({
                            "title": article.title,
                            "url": article.url,
                            "publisher": article.publisher,
                            "published_at": str(article.published_at) if article.published_at else None,
                            "content": article.content,
                            "metadata_": article.metadata_ or {},
                            "retry_count": 0,
                        }, default=str)
                        await redis_client.rpush("embedding:retry_queue", retry_payload)

                await db.commit()
                if failed_articles:
                    logger.warning(f"Deleted {len(failed_articles)} articles with failed embeddings; pushed {len(failed_articles)} to retry queue")
                logger.info(f"Embedded {embedded_count}/{len(articles_to_embed)} articles")

            # 5.5. 샘플링 품질 평가 (비용 절감) + MLOps 학습 데이터 수집
            try:
                from app.services.evaluator import evaluate_batch_sample
                eval_articles = [
                    {"title": a.title, "publisher": a.publisher, "keywords_data": (a.metadata_ or {}).get("keywords_data", {})}
                    for a in articles_to_embed[:20]
                ]
                eval_results = evaluate_batch_sample(eval_articles, sample_size=5)
                # 평가 결과를 DB에 저장 (MLOps 학습 데이터 수집)
                if eval_results:
                    try:
                        from app.services.ner_training_pipeline import save_evaluation_results
                        from app.services.model_manager import get_current_version
                        await save_evaluation_results(
                            eval_results,
                            model_version=get_current_version(),
                            session_factory=session_factory,
                        )
                    except Exception as save_err:
                        logger.warning(f"Failed to save evaluation results: {save_err}")
            except Exception as e:
                logger.warning(f"Sampling evaluation skipped: {e}")

        # 6. 상태 초기화 + 캐시 무효화 + 트렌드 캐시 워밍 + SSE 이벤트 발행
        await set_crawl_status("idle")
        from app.services.cache import invalidate_all_trend_caches, publish_event, cache_set
        await invalidate_all_trend_caches()

        # 트렌드 캐시 워밍: 3개 기간 미리 계산하여 Redis에 저장
        # 사용자 요청 시 즉시 응답 가능 (on-demand 계산 48초 → 캐시 <10ms)
        from app.core.trend_clustering import build_article_clusters
        warm_success_count = 0
        async with session_factory() as warm_db:
            for period in ("24h", "7d", "30d"):
                try:
                    result = await build_article_clusters(warm_db, period, min_cluster_size=1)
                    cache_key = f"trends:article-clusters:{period}:1"
                    await cache_set(cache_key, result.model_dump(), ttl=3600)
                    logger.info(f"Trend cache warmed: {period}")
                    warm_success_count += 1
                except Exception as e:
                    logger.warning(f"Trend cache warming failed for {period}: {e}")
        if warm_success_count == 0:
            logger.warning("All cache warming periods failed — setting cache:warm_failed flag")
            await cache_set("cache:warm_failed", 1, ttl=1800)

        await publish_event("stats_updated", {
            "type": "crawl_complete",
            "crawled": len(crawled),
            "embedded": len(articles_to_embed),
        })

        return {
            "status": "ok",
            "fetched": len(feed_urls),
            "crawled": len(crawled),
            "embedded": embedded_count,
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
    from app.models.request_log import RequestLog
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

            # request_logs 정리 (90일 초과 로그 삭제)
            old_request_logs_result = await db.execute(
                delete(RequestLog).where(RequestLog.created_at < cutoff)
            )
            deleted_request_logs = old_request_logs_result.rowcount
            logger.info(f"Deleted {deleted_request_logs} old request logs")

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
            result = {"status": "ok", "deleted": len(to_delete_ids), "deleted_logs": deleted_logs}

            try:
                from app.services.webhook import send_webhook
                send_webhook(
                    title="정리 완료",
                    description=f"{len(to_delete_ids)}건 삭제",
                    color=0xE67E22,
                )
            except Exception as _we:
                logger.warning(f"Webhook call failed (non-critical): {_we}")

            return result

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

            # 3. 원본 기사 임베딩 조회 또는 생성
            origin_kw = origin_meta.get("keywords_data", {})
            if origin.qdrant_point_id:
                # 이미 임베딩이 있으면 Qdrant에서 기존 벡터 조회 (Azure API 호출 불필요)
                from app.services.vector_store import retrieve_vectors
                _point_id = str(origin.qdrant_point_id)
                vectors = retrieve_vectors([_point_id])
                origin_embedding = vectors.get(_point_id)
                if not origin_embedding:
                    # Qdrant 조회 실패 시 Azure API로 재생성
                    text = get_article_text(origin.title)
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
            # [정책] 임베딩 실패 기사는 DB에서 삭제 — 벡터 검색 불가 기사 미보존
            if articles_needing_embed:
                # NER 키워드 추출 (아직 없는 기사만)
                for a in articles_needing_embed:
                    a_meta = dict(a.metadata_ or {})
                    if "keywords_data" not in a_meta:
                        kw_data = extract_keywords(a.title)
                        a_meta["keywords_data"] = kw_data
                        a.metadata_ = a_meta

                texts = [
                    get_article_text(a.title)
                    for a in articles_needing_embed
                ]
                embeddings = create_embeddings_batch(texts)
                embed_map = {}
                failed_ids = set()
                for article, embedding in zip(articles_needing_embed, embeddings):
                    if embedding is None:
                        logger.warning(f"Embedding failed, will delete article {article.id}: {article.title[:50]}")
                        failed_ids.add(str(article.id))
                        await db.delete(article)
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

                # 임베딩 실패 기사를 similar_articles에서도 제거
                if failed_ids:
                    similar_articles = [sa for sa in similar_articles if sa["id"] not in failed_ids]
                    logger.warning(f"Deleted {len(failed_ids)} articles with failed embeddings")

                # similar_articles에 임베딩 매핑
                for sa in similar_articles:
                    if sa["id"] in embed_map:
                        sa["embedding"] = embed_map[sa["id"]]

                logger.info(f"Batch embedded {len(articles_needing_embed) - len(failed_ids)}/{len(articles_needing_embed)} articles")

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

            try:
                from app.services.webhook import send_webhook
                send_webhook(
                    title="Live 추적 완료",
                    description=f"Live 추적 완료: {origin.title}",
                    color=0x3498DB,
                )
            except Exception as _we:
                logger.warning(f"Webhook call failed (non-critical): {_we}")

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


# ── Embedding Retry Queue ──


@celery_app.task(bind=True, soft_time_limit=120, time_limit=150)
def retry_failed_embeddings(self):
    """
    임베딩 실패 기사 재시도 태스크

    Redis embedding:retry_queue에서 최대 10건 팝 → 임베딩 재시도 → DB+Qdrant 저장
    3회 이상 실패 시 폐기. Celery Beat에 의해 15분마다 실행
    """
    try:
        return run_async(_run_retry_embeddings())
    except Exception as e:
        logger.error(f"retry_failed_embeddings failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


async def _run_retry_embeddings():
    """임베딩 재시도 파이프라인"""
    import json
    from app.services.cache import get_redis
    from app.services.embedding import create_embeddings_batch, get_article_text
    from app.services.vector_store import upsert_embedding
    from app.models.article import Article
    from app.services.keyword_extractor import extract_keywords

    redis_client = await get_redis()
    if not redis_client:
        return {"status": "skip", "reason": "redis_unavailable"}

    queue_len = await redis_client.llen("embedding:retry_queue")
    if queue_len == 0:
        return {"status": "ok", "retried": 0, "queue_remaining": 0}

    MAX_BATCH = 10
    MAX_RETRY_COUNT = 3
    items = []
    for _ in range(min(MAX_BATCH, queue_len)):
        raw = await redis_client.lpop("embedding:retry_queue")
        if not raw:
            break
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning("Invalid retry queue item, discarding")

    if not items:
        return {"status": "ok", "retried": 0, "queue_remaining": 0}

    texts = [get_article_text(item["title"]) for item in items]
    embeddings = create_embeddings_batch(texts)

    worker_engine, session_factory = _create_worker_engine()
    succeeded = 0
    re_queued = 0
    discarded = 0

    try:
        async with session_factory() as db:
            from sqlalchemy import select
            for item, embedding in zip(items, embeddings):
                retry_count = item.get("retry_count", 0)

                if embedding is None:
                    if retry_count + 1 >= MAX_RETRY_COUNT:
                        discarded += 1
                        logger.warning(f"Discarding article after {MAX_RETRY_COUNT} retries: {item['title'][:50]}")
                    else:
                        item["retry_count"] = retry_count + 1
                        await redis_client.rpush("embedding:retry_queue", json.dumps(item, default=str))
                        re_queued += 1
                    continue

                result = await db.execute(
                    select(Article).where(Article.url == item["url"])
                )
                existing = result.scalar_one_or_none()
                if existing and existing.qdrant_point_id:
                    succeeded += 1
                    continue

                if existing:
                    article = existing
                else:
                    # published_at를 datetime으로 복원 (Redis JSON 직렬화 시 문자열로 변환됨)
                    pub_at_raw = item.get("published_at")
                    pub_at = None
                    if pub_at_raw:
                        try:
                            from datetime import datetime as _dt
                            pub_at = _dt.fromisoformat(pub_at_raw)
                        except (ValueError, TypeError):
                            logger.warning(f"Failed to parse published_at: {pub_at_raw}")
                    article = Article(
                        title=item["title"],
                        url=item["url"],
                        publisher=item.get("publisher"),
                        published_at=pub_at,
                        content=item.get("content"),
                        metadata_=item.get("metadata_", {}),
                    )
                    db.add(article)
                    await db.flush()

                meta = dict(article.metadata_ or {})
                if "keywords_data" not in meta:
                    meta["keywords_data"] = extract_keywords(article.title)
                    article.metadata_ = meta

                kw_data = meta.get("keywords_data", {})
                payload = {
                    "title": article.title,
                    "publisher": article.publisher,
                    "published_at": str(article.published_at) if article.published_at else None,
                    "keywords": kw_data.get("keywords", []),
                }
                point_id = upsert_embedding(str(article.id), embedding, payload)
                article.qdrant_point_id = point_id
                succeeded += 1

            await db.commit()
    finally:
        await worker_engine.dispose()

    remaining = await redis_client.llen("embedding:retry_queue")
    logger.info(f"Retry embeddings: {succeeded} succeeded, {re_queued} re-queued, {discarded} discarded, {remaining} remaining")
    return {"status": "ok", "retried": succeeded, "re_queued": re_queued, "discarded": discarded, "queue_remaining": remaining}


# ── Worker Memory Monitoring ──


@celery_app.task(bind=True, soft_time_limit=30, time_limit=45)
def check_worker_memory(self):
    """
    Celery Worker 메모리 모니터링 태스크

    psutil로 현재 프로세스 RSS 확인 → 800MB 경고, 950MB 위험
    Celery Beat에 의해 5분마다 실행
    """
    import os

    try:
        import psutil
    except ImportError:
        logger.warning("psutil not installed, skipping memory check")
        return {"status": "skip", "reason": "psutil_not_installed"}

    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)

    WARN_THRESHOLD_MB = 1400
    CRITICAL_THRESHOLD_MB = 1700

    status = "ok"
    if rss_mb >= CRITICAL_THRESHOLD_MB:
        status = "critical"
        logger.error(f"Worker memory CRITICAL: {rss_mb:.0f}MB (threshold: {CRITICAL_THRESHOLD_MB}MB)")
        try:
            from app.services.webhook import send_webhook
            send_webhook(
                title="Worker 메모리 위험",
                description=f"RSS: {rss_mb:.0f}MB / {CRITICAL_THRESHOLD_MB}MB 임계치 초과",
                color=0xE74C3C,
            )
        except Exception:
            pass
    elif rss_mb >= WARN_THRESHOLD_MB:
        status = "warning"
        logger.warning(f"Worker memory WARNING: {rss_mb:.0f}MB (threshold: {WARN_THRESHOLD_MB}MB)")

    # Redis heartbeat for dashboard health check (solo pool can't respond to inspect while busy)
    try:
        import redis as _redis
        from app.config import get_settings
        _r = _redis.Redis.from_url(get_settings().redis_url)
        _r.setex("celery:worker:heartbeat", 600, f"{rss_mb:.0f}")

        # NER 모델 로딩 상태도 함께 저장 (개요 대시보드 서비스 상태 표시용)
        try:
            from app.services.keyword_extractor import get_extractor
            ext = get_extractor()
            ner_info = {
                "loaded": ext._loaded,
                "use_bert": ext._use_bert_ner if ext._loaded else None,
                "kiwi_loaded": ext._kiwi is not None,
                "model_path": ext._loaded_model_path,
                "model_version": ext.get_model_version() if ext._loaded else None,
            }
            _r.setex("celery:worker:ner_status", 600, json.dumps(ner_info))
        except Exception:
            pass

        _r.close()
    except Exception:
        pass

    return {"status": status, "rss_mb": round(rss_mb, 1), "pid": os.getpid()}


# ── NER MLOps Tasks ──


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def collect_ner_training_data(self):
    """
    NER 학습 데이터 수집 태스크

    미평가 기사에서 샘플링 → GPT function calling 평가 → DB 저장
    Celery Beat에 의해 6시간마다 실행
    """
    try:
        return run_async(_run_collect_ner_training())
    except Exception as e:
        logger.error(f"collect_ner_training_data failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


async def _run_collect_ner_training():
    """NER 학습 데이터 수집 파이프라인"""
    from sqlalchemy import select, func as sa_func
    from app.models.article import Article
    from app.models.ner_training import NerTrainingSample
    from app.config import get_settings

    settings = get_settings()
    worker_engine, session_factory = _create_worker_engine()

    try:
        async with session_factory() as db:
            # 이미 평가된 기사 제목 목록
            evaluated_result = await db.execute(
                select(NerTrainingSample.title)
            )
            evaluated_titles = {row[0] for row in evaluated_result.all()}

            # 키워드가 추출된 기사 중 미평가 기사 샘플링
            # AI 학습 금지 언론사(한겨레 등) 제외
            query = select(Article).where(
                Article.metadata_.isnot(None),
            )
            if settings.ner_excluded_publishers:
                query = query.where(~Article.publisher.in_(settings.ner_excluded_publishers))
            result = await db.execute(
                query.order_by(sa_func.random()).limit(settings.ner_eval_sample_size * 2)
            )
            candidates = result.scalars().all()

            # 이미 평가된 기사 제외
            articles = [
                a for a in candidates
                if a.title not in evaluated_titles
                and (a.metadata_ or {}).get("keywords_data")
            ][:settings.ner_eval_sample_size]

        if not articles:
            logger.info("No unevaluated articles found for NER training data collection")
            return {"status": "ok", "evaluated": 0, "saved": 0}

        # GPT function calling 평가 + DB 저장
        from app.services.ner_evaluation_agent import evaluate_and_correct
        from app.services.ner_training_pipeline import convert_to_bio_tags, save_training_sample
        from app.services.model_manager import get_current_version

        model_version = get_current_version()
        evaluated = 0
        saved = 0

        for article in articles:
            try:
                keywords_data = (article.metadata_ or {}).get("keywords_data", {})
                correction = evaluate_and_correct(article.title, keywords_data)
                evaluated += 1

                if not correction.success or correction.quality_score < settings.ner_eval_min_quality:
                    continue

                bio_tags = convert_to_bio_tags(article.title, correction.corrected_entities)

                sample_id = await save_training_sample(
                    session_factory=session_factory,
                    article_id=str(article.id),
                    title=article.title,
                    bio_tags=bio_tags,
                    gpt_quality_score=correction.quality_score,
                    gpt_corrected_entities=correction.corrected_entities,
                    original_entities=keywords_data.get("entities", []),
                    gpt_reasoning=correction.reasoning,
                    model_version=model_version,
                    extraction_method=keywords_data.get("method", "unknown"),
                )

                if sample_id:
                    saved += 1

            except Exception as e:
                logger.warning(f"NER eval failed for '{article.title[:50]}': {e}")
                continue

        logger.info(f"NER training data collection: {evaluated} evaluated, {saved} saved")
        return {"status": "ok", "evaluated": evaluated, "saved": saved}

    finally:
        await worker_engine.dispose()


@celery_app.task(bind=True, soft_time_limit=60, time_limit=90)
def check_training_readiness(self):
    """
    NER fine-tuning 준비 상태 확인 태스크

    미사용 학습 데이터 건수 확인 → 임계치 초과 시 알림
    Celery Beat에 의해 매일 02:00에 실행
    """
    try:
        return run_async(_run_check_readiness())
    except Exception as e:
        logger.error(f"check_training_readiness failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


async def _run_check_readiness():
    """학습 준비 상태 확인"""
    from sqlalchemy import select, func as sa_func
    from app.models.ner_training import NerTrainingSample
    from app.config import get_settings

    settings = get_settings()
    worker_engine, session_factory = _create_worker_engine()

    try:
        async with session_factory() as db:
            result = await db.execute(
                select(sa_func.count(NerTrainingSample.id)).where(
                    NerTrainingSample.is_used_for_training == False  # noqa: E712
                )
            )
            unused_count = result.scalar() or 0

            total_result = await db.execute(
                select(sa_func.count(NerTrainingSample.id))
            )
            total_count = total_result.scalar() or 0

        ready = unused_count >= settings.ner_training_min_samples
        status = "ready" if ready else "collecting"
        auto_triggered = False

        logger.info(
            f"NER training readiness: {unused_count} unused / {total_count} total "
            f"(threshold: {settings.ner_training_min_samples}) — {status}"
        )

        if ready:

            try:
                from app.services.webhook import send_webhook
                send_webhook(
                    title="NER Fine-tuning 준비 완료",
                    description=(
                        f"미사용 학습 데이터 {unused_count}건 (임계치: {settings.ner_training_min_samples}건)\n"
                        "자동 Fine-tuning 트리거됨"
                    ),
                    color=0x9B59B6,
                )
            except Exception as _we:
                logger.warning(f"Webhook call failed (non-critical): {_we}")

            # 자동 Fine-tuning 트리거
            try:
                trigger_bert_finetune.delay()
                auto_triggered = True
                logger.info(
                    f"Auto-triggered BERT fine-tuning: {unused_count} unused samples "
                    f"(threshold: {settings.ner_training_min_samples})"
                )
            except Exception as ft_err:
                logger.warning(f"Auto fine-tuning trigger failed: {ft_err}")

        return {
            "status": status,
            "unused_samples": unused_count,
            "total_samples": total_count,
            "threshold": settings.ner_training_min_samples,
            "auto_triggered": auto_triggered,
        }

    finally:
        await worker_engine.dispose()


@celery_app.task(bind=True, soft_time_limit=60, time_limit=90)
def trigger_bert_finetune(self):
    """
    BERT NER fine-tuning 트리거 — 별도 Docker 컨테이너로 실행

    Docker SDK로 newsorigin-finetune 컨테이너를 detach 모드로 시작.
    워커 블로킹 없이 즉시 반환 (~2h 학습은 별도 컨테이너에서 진행).
    대시보드 /admin/mlops에서 컨테이너 상태 실시간 모니터링 가능.
    """
    import os

    CONTAINER_NAME = "newsorigin-finetune"

    try:
        import docker
    except ImportError:
        logger.error("docker SDK not installed — pip install docker>=7.0.0")
        return {"status": "error", "error": "docker SDK not installed"}

    try:
        client = docker.from_env()

        # 중복 실행 방지: 기존 컨테이너 상태 확인
        try:
            existing = client.containers.get(CONTAINER_NAME)
            if existing.status == "running":
                logger.warning(f"Finetune container already running: {existing.short_id}")
                return {
                    "status": "skipped",
                    "reason": "already_running",
                    "container_id": existing.short_id,
                }
            # exited/created 상태면 제거 후 새로 시작
            existing.remove(force=True)
            logger.info(f"Removed stale finetune container: {existing.short_id}")
        except docker.errors.NotFound:
            pass

        # 현재 워커 컨테이너에서 image, network, volume 정보 자동 추출
        import socket
        hostname = socket.gethostname()
        worker_image = None
        network_name = None
        volume_name = None

        try:
            worker = client.containers.get(hostname)
            # image
            tags = worker.image.tags
            worker_image = tags[0] if tags else worker.image.id
            # network (docker-compose 기본 네트워크)
            nets = list(worker.attrs["NetworkSettings"]["Networks"].keys())
            network_name = nets[0] if nets else None
            # bert_models 볼륨 이름
            for mount in worker.attrs.get("Mounts", []):
                if mount.get("Destination") == "/app/models/bert-ner" and mount.get("Type") == "volume":
                    volume_name = mount["Name"]
                    break
        except Exception as e:
            logger.warning(f"Worker container inspect failed (using fallback): {e}")

        if not worker_image:
            # fallback: newsorigin-finetune 이미지 또는 worker 이미지 추정
            for candidate in ["news-origin-finetune", "news-origin-celery-worker", "news-origin-backend"]:
                try:
                    client.images.get(candidate)
                    worker_image = candidate
                    break
                except docker.errors.ImageNotFound:
                    continue
            if not worker_image:
                return {"status": "error", "error": "finetune image not found"}

        # 환경변수 (워커 환경에서 필요한 변수만 전달)
        env_keys = [
            "DATABASE_URL", "BERT_MODEL_NAME", "NER_MODEL_BASE_DIR",
            "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_MODEL_NAME", "AZURE_OPENAI_API_VERSION",
            "APP_SECRET_KEY", "WEBHOOK_URL",
        ]
        env_vars = {k: os.environ[k] for k in env_keys if k in os.environ}

        # 볼륨 설정
        volumes = {}
        if volume_name:
            volumes[volume_name] = {"bind": "/app/models/bert-ner", "mode": "rw"}

        # 볼륨 권한 초기화 (appuser UID=1000이 쓰기 가능하도록)
        if volume_name:
            try:
                client.containers.run(
                    image=worker_image,
                    command="chown -R 1000:1000 /app/models/bert-ner",
                    user="root",
                    volumes={volume_name: {"bind": "/app/models/bert-ner", "mode": "rw"}},
                    remove=True,
                )
                logger.info("Finetune volume permissions initialized (chown appuser)")
            except Exception as e:
                logger.warning(f"Volume permission init failed (may already be correct): {e}")

        # 컨테이너 시작 (detach 모드)
        run_kwargs = {
            "image": worker_image,
            "command": "python3 -m scripts.finetune_bert_ner",
            "name": CONTAINER_NAME,
            "detach": True,
            "environment": env_vars,
            "volumes": volumes,
            "mem_limit": "2g",
            "auto_remove": False,
        }
        if network_name:
            run_kwargs["network"] = network_name

        container = client.containers.run(**run_kwargs)
        logger.info(f"Finetune container started: {container.short_id} (image: {worker_image})")

        try:
            from app.services.webhook import send_webhook
            send_webhook(
                title="Fine-tuning 시작",
                description=f"별도 컨테이너에서 BERT NER fine-tuning 시작 ({container.short_id})",
                color=0x9B59B6,
            )
        except Exception:
            pass

        return {
            "status": "started",
            "container_id": container.short_id,
            "image": worker_image,
        }

    except Exception as e:
        logger.error(f"Failed to start finetune container: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def reextract_keywords_batch(self):
    """
    모델 교체 후 최근 기사 키워드 재추출 태스크

    새 BERT NER 모델로 최근 N일 기사의 키워드를 재추출
    """
    try:
        return run_async(_run_reextract())
    except Exception as e:
        logger.error(f"reextract_keywords_batch failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


async def _run_reextract():
    """키워드 재추출 파이프라인"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.services.keyword_extractor import get_extractor
    from app.config import get_settings

    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.ner_reextract_days)

    worker_engine, session_factory = _create_worker_engine()

    try:
        # 기존 추출기 캐시 무효화 (새 모델 로딩 강제)
        extractor = get_extractor()
        extractor._loaded = False
        extractor._ner_pipeline = None

        async with session_factory() as db:
            result = await db.execute(
                select(Article).where(
                    Article.created_at >= cutoff,
                    Article.metadata_.isnot(None),
                ).order_by(Article.created_at.desc())
            )
            articles = result.scalars().all()

            if not articles:
                return {"status": "ok", "reextracted": 0}

            reextracted = 0
            for article in articles:
                try:
                    new_kw = extractor.extract(article.title)
                    meta = dict(article.metadata_ or {})
                    meta["keywords_data"] = new_kw
                    article.metadata_ = meta
                    reextracted += 1
                except Exception as e:
                    logger.warning(f"Re-extraction failed for '{article.title[:50]}': {e}")

            await db.commit()

        logger.info(f"Re-extracted keywords for {reextracted}/{len(articles)} articles")

        # 트렌드 캐시 무효화 + 워밍 (새 키워드 기반 클러스터 즉시 반영)
        cache_warmed = False
        try:
            from app.services.cache import invalidate_all_trend_caches, cache_set
            from app.core.trend_clustering import build_article_clusters
            await invalidate_all_trend_caches()

            warm_count = 0
            async with session_factory() as warm_db:
                for period in ("24h", "7d", "30d"):
                    try:
                        result = await build_article_clusters(warm_db, period, min_cluster_size=1)
                        cache_key = f"trends:article-clusters:{period}:1"
                        await cache_set(cache_key, result.model_dump(), ttl=3600)
                        warm_count += 1
                        logger.info(f"Reextract cache warmed: {period}")
                    except Exception as e:
                        logger.warning(f"Reextract cache warming failed for {period}: {e}")
            cache_warmed = warm_count > 0
        except Exception as e:
            logger.warning(f"Reextract cache invalidation failed (non-critical): {e}")

        # MLOps 대시보드용 최근 재추출 결과 저장
        try:
            from app.services.cache import cache_set as _cache_set
            model_ver = extractor.get_model_version() if extractor else "unknown"
            await _cache_set("mlops:last_reextract", {
                "reextracted": reextracted,
                "total": len(articles),
                "model_version": model_ver,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "cache_warmed": cache_warmed,
            }, ttl=86400 * 30)
        except Exception:
            pass

        return {"status": "ok", "reextracted": reextracted, "total": len(articles)}

    finally:
        await worker_engine.dispose()


# ── Admin Report Tasks ──

@celery_app.task(name="app.workers.tasks.generate_weekly_report")
def generate_weekly_report():
    """주간 리포트 생성 + 이메일 발송"""
    return run_async(_generate_report("weekly"))


@celery_app.task(name="app.workers.tasks.generate_monthly_report")
def generate_monthly_report():
    """월간 리포트 생성 + 이메일 발송"""
    return run_async(_generate_report("monthly"))


async def _generate_report(report_type: str):
    """정기 리포트 생성 + 이메일 발송 공통 로직"""
    from app.services.report_generator import generate_periodic_report
    from app.services.email_sender import send_report_email

    worker_engine, session_factory = _create_worker_engine()
    try:
        async with session_factory() as session:
            report = await generate_periodic_report(session, report_type)
            logger.info(f"[{report_type}] 리포트 생성 완료: {report.title}")

            # 이메일 발송
            try:
                narrative = None
                if report.content_json and isinstance(report.content_json, dict):
                    narrative = report.content_json.get("narrative")
                sent = send_report_email(
                    title=report.title,
                    summary=report.summary,
                    report_type=report_type,
                    severity="info",
                    report_id=str(report.id),
                    narrative=narrative,
                )
                if sent:
                    report.email_sent = True
                    report.email_sent_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(f"[{report_type}] 리포트 이메일 발송 완료")
            except Exception as e:
                report.email_error = str(e)[:500]
                await session.commit()
                logger.warning(f"[{report_type}] 리포트 이메일 발송 실패: {e}")

            return {"status": "ok", "report_id": str(report.id), "title": report.title}
    finally:
        await worker_engine.dispose()


@celery_app.task(name="app.workers.tasks.check_system_alerts")
def check_system_alerts():
    """시스템 알림 체크 → 비정기 리포트 생성 + 이메일 발송"""
    return run_async(_check_system_alerts())


async def _check_system_alerts():
    """시스템 알림 감지 + 리포트 생성 + 이메일 발송"""
    from app.services.alert_detector import check_all_alerts
    from app.services.report_generator import generate_alert_report
    from app.services.email_sender import send_report_email

    worker_engine, session_factory = _create_worker_engine()
    try:
        async with session_factory() as session:
            alerts = await check_all_alerts(session)

            if not alerts:
                return {"status": "ok", "alerts": 0}

            results = []
            for alert in alerts:
                try:
                    report = await generate_alert_report(
                        session=session,
                        category=alert["category"],
                        severity=alert["severity"],
                        title=alert["title"],
                        summary=alert["summary"],
                        details=alert["details"],
                    )

                    # 이메일 발송
                    try:
                        sent = send_report_email(
                            title=report.title,
                            summary=report.summary,
                            report_type="alert",
                            severity=alert["severity"],
                            report_id=str(report.id),
                        )
                        if sent:
                            report.email_sent = True
                            report.email_sent_at = datetime.now(timezone.utc)
                            await session.commit()
                    except Exception as e:
                        report.email_error = str(e)[:500]
                        await session.commit()
                        logger.warning(f"알림 이메일 발송 실패 [{alert['category']}]: {e}")

                    results.append({
                        "category": alert["category"],
                        "severity": alert["severity"],
                        "report_id": str(report.id),
                    })
                except Exception as e:
                    logger.error(f"알림 리포트 생성 실패 [{alert['category']}]: {e}")

            logger.info(f"시스템 알림 체크 완료: {len(alerts)}건 감지, {len(results)}건 리포트 생성")
            return {"status": "ok", "alerts": len(alerts), "reports": results}
    finally:
        await worker_engine.dispose()