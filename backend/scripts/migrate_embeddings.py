"""
# migrate_embeddings.py - 임베딩 마이그레이션 스크립트
# Description: 기존 관계 초기화 → Qdrant 컬렉션 재생성 → 전체 NER + 재임베딩
#
# 사용법:
#   cd backend
#   python -m scripts.migrate_embeddings
#
# 주의: 이 스크립트는 timeline_entries, tracking_requests를 초기화합니다.
"""

import asyncio
import logging
import sys
import os

# backend 디렉토리를 모듈 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from sqlalchemy import delete, update, select, func
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from qdrant_client import models as qmodels

    from app.config import get_settings
    from app.models.article import Article
    from app.models.timeline import TimelineEntry, TrackingRequest
    from app.services.vector_store import get_qdrant_client
    from app.services.embedding import create_embeddings_batch, get_article_text
    from app.services.keyword_extractor import extract_keywords

    settings = get_settings()

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Step 1: 기존 관계 초기화
    logger.info("=== Step 1: 기존 관계 초기화 ===")
    async with session_factory() as db:
        # timeline_entries 삭제
        result = await db.execute(delete(TimelineEntry))
        logger.info(f"Deleted {result.rowcount} timeline entries")

        # tracking_requests 초기화
        result = await db.execute(delete(TrackingRequest))
        logger.info(f"Deleted {result.rowcount} tracking requests")

        # qdrant_point_id 초기화
        result = await db.execute(
            update(Article).values(qdrant_point_id=None)
        )
        logger.info(f"Reset qdrant_point_id for {result.rowcount} articles")

        await db.commit()

    # Step 2: Qdrant 컬렉션 재생성 (1024차원)
    logger.info("=== Step 2: Qdrant 컬렉션 재생성 ===")
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted old collection: {collection_name}")
    except Exception as e:
        logger.warning(f"Collection delete skipped: {e}")

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=settings.embedding_dimension,
            distance=qmodels.Distance.COSINE,
        ),
    )
    logger.info(f"Created new collection: {collection_name} ({settings.embedding_dimension}d)")

    # Step 3: 전체 기사 NER 키워드 추출 + Azure 임베딩 재생성
    logger.info("=== Step 3: 전체 기사 NER + 재임베딩 ===")
    BATCH = 16

    async with session_factory() as db:
        # 전체 기사 수
        count_result = await db.execute(select(func.count(Article.id)))
        total = count_result.scalar()
        logger.info(f"Total articles to process: {total}")

        # 배치 처리
        offset = 0
        processed = 0

        while offset < total:
            result = await db.execute(
                select(Article)
                .order_by(Article.created_at)
                .offset(offset)
                .limit(BATCH)
            )
            batch = result.scalars().all()
            if not batch:
                break

            # NER 키워드 추출
            for article in batch:
                meta = dict(article.metadata_ or {})
                kw_data = extract_keywords(article.title)
                meta["keywords_data"] = kw_data
                article.metadata_ = meta

            # Azure 임베딩 생성
            texts = [get_article_text(a.title) for a in batch]
            try:
                embeddings = create_embeddings_batch(texts)
            except Exception as e:
                logger.error(f"Embedding batch failed at offset {offset}: {e}")
                offset += BATCH
                continue

            # Qdrant 저장
            import uuid
            points = []
            for article, embedding in zip(batch, embeddings):
                point_id = str(uuid.uuid4())
                article_meta = article.metadata_ or {}
                kw_data = article_meta.get("keywords_data", {})
                points.append(qmodels.PointStruct(
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
                article.qdrant_point_id = point_id

            client.upsert(collection_name=collection_name, points=points)
            await db.commit()

            processed += len(batch)
            offset += BATCH
            logger.info(f"Processed {processed}/{total} articles")

    # Step 4: 캐시 무효화
    logger.info("=== Step 4: 캐시 무효화 ===")
    try:
        from app.services.cache import cache_delete
        cache_keys = [
            "trends:stats", "trends:hot:24h", "trends:hot:7d", "trends:hot:30d",
            "trends:popular",
            "trends:article-clusters:24h:1", "trends:article-clusters:24h:2",
            "trends:article-clusters:7d:1", "trends:article-clusters:7d:2",
            "trends:article-clusters:30d:1", "trends:article-clusters:30d:2",
            "trends:recent-articles:30:all",
        ]
        for key in cache_keys:
            await cache_delete(key)
        logger.info("Cache invalidated")
    except Exception as e:
        logger.warning(f"Cache invalidation failed (non-critical): {e}")

    await engine.dispose()
    logger.info("=== Migration complete ===")
    logger.info(f"Total processed: {processed} articles")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="임베딩 마이그레이션 (관계 초기화 + 재임베딩)")
    parser.add_argument("--force", action="store_true", help="확인 없이 즉시 실행")
    args = parser.parse_args()

    if not args.force:
        print("=" * 60)
        print("⚠ 이 스크립트는 다음 데이터를 삭제합니다:")
        print("  - 모든 timeline_entries")
        print("  - 모든 tracking_requests")
        print("  - Qdrant 컬렉션 재생성 (기존 벡터 삭제)")
        print()
        print("실행 전 DB 백업을 권장합니다:")
        print("  pg_dump newsorigin > backup_$(date +%F).sql")
        print("=" * 60)
        confirm = input("계속하시겠습니까? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("취소되었습니다.")
            sys.exit(0)

    asyncio.run(main())
