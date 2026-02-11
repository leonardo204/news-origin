"""
# tasks.py - Celery Async Tasks
# Version: 0.2.0
# Description: 기사 분석 파이프라인 (크롤링 → 임베딩 → 유사도 → 타임라인)
"""

import asyncio
import logging
from datetime import datetime

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
    """비동기 분석 파이프라인 실행"""
    from sqlalchemy import select
    from app.models.article import Article
    from app.models.timeline import TrackingRequest, TimelineEntry
    from app.core.crawler import crawl_article, crawl_articles_batch
    from app.core.analyzer import analyze_article, find_similar_articles
    from app.core.timeline import build_timeline
    from app.services.news_search import search_news

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

            # 4. 유사 기사 크롤링
            urls = [r["url"] for r in search_results if r["url"] != origin.url]
            crawled = await crawl_articles_batch(urls[:20])
            tracking.progress = 60
            await db.commit()

            # 5. 크롤링된 기사 DB 저장 + 임베딩 생성
            similar_articles = []
            seen_ids = {str(origin.id)}  # Exclude origin article
            for article_data in crawled:
                # DB upsert
                existing = await db.execute(
                    select(Article).where(Article.url == article_data["url"])
                )
                article = existing.scalar_one_or_none()
                if not article:
                    article = Article(**article_data)
                    db.add(article)
                    await db.flush()

                # Skip origin or duplicates
                aid = str(article.id)
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)

                # 임베딩 생성 + Qdrant 저장
                pt_id, embedding = analyze_article(
                    article_id=aid,
                    title=article.title,
                    content=article.content,
                    publisher=article.publisher,
                    published_at=str(article.published_at) if article.published_at else None,
                )
                article.qdrant_point_id = pt_id

                similar_articles.append({
                    "id": aid,
                    "title": article.title,
                    "published_at": article.published_at,
                    "publisher": article.publisher,
                    "embedding": embedding,
                })

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

            # 7. 타임라인 구성
            origin_data = {
                "id": str(origin.id),
                "title": origin.title,
                "published_at": origin.published_at,
            }
            timeline_entries = build_timeline(origin_data, similar_articles)

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
