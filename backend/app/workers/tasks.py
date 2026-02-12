"""
# tasks.py - Celery Async Tasks
# Version: 0.3.0
# Description: 기사 분석 파이프라인 + 백그라운드 크롤링
# Changes:
#   - 0.2.0: 기사 분석 파이프라인 (크롤링 → 임베딩 → 유사도 → 타임라인)
#   - 0.3.0: fetch_trending_news, cleanup_old_articles, 파이프라인 최적화
"""

import asyncio
import logging
from datetime import datetime, timedelta

from celery.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _create_worker_engine():
    """Celery 워커 전용 DB 엔진 생성 (이벤트 루프 충돌 방지)"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import get_settings

    settings = get_settings()
    worker_engine = create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        pool_size=5,
        max_overflow=2,
    )
    factory = async_sessionmaker(
        worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return worker_engine, factory


# ── Background Crawling Tasks ──


@celery_app.task(bind=True, soft_time_limit=540, time_limit=600)
def fetch_trending_news(self):
    """
    백그라운드 트렌딩 뉴스 크롤링 태스크

    카테고리 RSS 피드 수집 → DB 중복 체크 → 배치 크롤링 → 배치 임베딩 → 저장
    Celery Beat에 의해 30분마다 실행
    """
    from app.config import get_settings
    settings = get_settings()

    if not settings.background_crawl_enabled:
        logger.info("Background crawling is disabled")
        return {"status": "disabled"}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_fetch_trending())
        return result
    except SoftTimeLimitExceeded:
        logger.error("fetch_trending_news timed out")
        return {"status": "timeout"}
    except Exception as e:
        logger.error(f"fetch_trending_news failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}
    finally:
        loop.close()


async def _run_fetch_trending():
    """백그라운드 트렌딩 뉴스 수집 파이프라인"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.core.crawler import crawl_articles_batch
    from app.services.embedding import create_embeddings_batch, get_article_text
    from app.services.vector_store import upsert_embedding
    from app.services.news_feed import fetch_all_category_feeds
    from app.workers.beat_schedule import (
        CATEGORY_FEEDS, CRAWL_BATCH_SIZE, MAX_ARTICLES_PER_RUN,
        FEED_LIMIT_PER_CATEGORY,
    )

    worker_engine, session_factory = _create_worker_engine()
    try:
        # 1. 카테고리 피드 수집
        feed_articles = await fetch_all_category_feeds(
            CATEGORY_FEEDS,
            limit_per_category=FEED_LIMIT_PER_CATEGORY,
            max_total=MAX_ARTICLES_PER_RUN,
        )
        if not feed_articles:
            logger.info("No articles from feeds")
            return {"status": "ok", "fetched": 0, "crawled": 0, "embedded": 0}

        feed_urls = [a["url"] for a in feed_articles]

        # 2. DB에서 이미 존재하는 URL 확인
        async with session_factory() as db:
            result = await db.execute(
                select(Article.url, Article.qdrant_point_id).where(
                    Article.url.in_(feed_urls)
                )
            )
            existing = {row.url: row.qdrant_point_id for row in result.all()}

        urls_to_crawl = [u for u in feed_urls if u not in existing]
        logger.info(
            f"Feed articles: {len(feed_urls)}, "
            f"already in DB: {len(existing)}, "
            f"to crawl: {len(urls_to_crawl)}"
        )

        if not urls_to_crawl:
            return {"status": "ok", "fetched": len(feed_urls), "crawled": 0, "embedded": 0}

        # 3. 미크롤링 기사 배치 크롤링
        crawled = await crawl_articles_batch(urls_to_crawl[:CRAWL_BATCH_SIZE])
        logger.info(f"Crawled {len(crawled)} articles")

        if not crawled:
            return {"status": "ok", "fetched": len(feed_urls), "crawled": 0, "embedded": 0}

        # 4. DB 저장 + 임베딩 생성
        articles_to_embed = []
        async with session_factory() as db:
            # feed_category 매핑 (feed_articles에서 URL → category)
            url_category_map = {
                a["url"]: a.get("feed_category")
                for a in feed_articles if "feed_category" in a
            }

            for article_data in crawled:
                # DB upsert
                result = await db.execute(
                    select(Article).where(Article.url == article_data["url"])
                )
                article = result.scalar_one_or_none()
                if not article:
                    # feed_category를 metadata에 저장
                    cat = url_category_map.get(article_data["url"])
                    if cat:
                        meta = article_data.get("metadata_", {}) or {}
                        meta["feed_category"] = cat
                        article_data["metadata_"] = meta
                    article = Article(**article_data)
                    db.add(article)
                    await db.flush()

                # 임베딩이 없는 기사만 수집
                if not article.qdrant_point_id:
                    articles_to_embed.append(article)

            await db.commit()

            # 5. 배치 임베딩 생성 + Qdrant 저장
            if articles_to_embed:
                texts = [
                    get_article_text(a.title, a.content)
                    for a in articles_to_embed
                ]
                embeddings = create_embeddings_batch(texts)

                for article, embedding in zip(articles_to_embed, embeddings):
                    payload = {
                        "title": article.title,
                        "publisher": article.publisher,
                        "published_at": str(article.published_at) if article.published_at else None,
                    }
                    point_id = upsert_embedding(str(article.id), embedding, payload)
                    article.qdrant_point_id = point_id

                await db.commit()
                logger.info(f"Embedded {len(articles_to_embed)} articles")

        # 6. 캐시 무효화 + SSE 이벤트 발행
        from app.services.cache import cache_delete, publish_event
        await cache_delete("trends:stats")
        await cache_delete("trends:hot:24h")
        await cache_delete("trends:hot:7d")
        await cache_delete("trends:hot:30d")
        await cache_delete("trends:popular")
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_cleanup())
        return result
    except Exception as e:
        logger.error(f"cleanup_old_articles failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}
    finally:
        loop.close()


async def _run_cleanup():
    """오래된 기사 삭제 파이프라인"""
    from sqlalchemy import select, delete, func
    from app.models.article import Article
    from app.models.timeline import TimelineEntry
    from app.services.vector_store import get_qdrant_client
    from app.config import get_settings

    settings = get_settings()
    cutoff = datetime.utcnow() - timedelta(days=settings.article_retention_days)

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

            if not to_delete_ids:
                logger.info("No old articles to clean up")
                return {"status": "ok", "deleted": 0}

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
            return {"status": "ok", "deleted": len(to_delete_ids)}

    finally:
        await worker_engine.dispose()


# ── Article Propagation Analysis Task ──


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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _run_pipeline(self, tracking_id, article_id)
        )
    except SoftTimeLimitExceeded:
        logger.error(f"Task timed out: tracking_id={tracking_id}")
        loop.run_until_complete(
            _mark_failed(tracking_id, "분석 시간이 초과되었습니다. (10분 제한)")
        )
    finally:
        loop.close()


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

            # 2. 원본 기사 임베딩 생성
            point_id, origin_embedding = analyze_article(
                article_id=str(origin.id),
                title=origin.title,
                content=origin.content,
                publisher=origin.publisher,
                published_at=str(origin.published_at) if origin.published_at else None,
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
            for article_data in crawled:
                result = await db.execute(
                    select(Article).where(Article.url == article_data["url"])
                )
                article = result.scalar_one_or_none()
                if not article:
                    article = Article(**article_data)
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

            # 배치 임베딩 (임베딩 없는 기사만)
            if articles_needing_embed:
                texts = [
                    get_article_text(a.title, a.content)
                    for a in articles_needing_embed
                ]
                embeddings = create_embeddings_batch(texts)
                embed_map = {}
                for article, embedding in zip(articles_needing_embed, embeddings):
                    payload = {
                        "title": article.title,
                        "publisher": article.publisher,
                        "published_at": str(article.published_at) if article.published_at else None,
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
            tracking.completed_at = datetime.utcnow()

            # Invalidate trend caches
            from app.services.cache import cache_delete
            await cache_delete("trends:hot:24h")
            await cache_delete("trends:hot:7d")
            await cache_delete("trends:hot:30d")
            await cache_delete("trends:popular")
            await cache_delete("trends:stats")

            await db.commit()
            logger.info(f"Pipeline completed: tracking_id={tracking_id}, articles={len(similar_articles)}")

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
