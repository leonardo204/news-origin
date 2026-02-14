"""
# trend_clustering.py - Article Trend Clustering Service
# Version: 0.1.0
# Description: Qdrant 벡터 유사도 기반 기사 클러스터링으로 트렌딩 토픽 추출
# Changes:
#   - 0.1.0: Greedy 클러스터링 알고리즘, 메타데이터 계산
"""

import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.schemas.search import (
    ArticleTrendsResponse,
    ClusterArticle,
    TopicCluster,
)
from app.services.vector_store import retrieve_vectors, search_similar

logger = logging.getLogger(__name__)

# 클러스터링 설정
CLUSTER_SIMILARITY_THRESHOLD = 0.75  # derivative 이상
MAX_ARTICLES_FOR_CLUSTERING = 500
MAX_CLUSTERS = 20
MAX_ARTICLES_PER_CLUSTER_RESPONSE = 10  # 응답에 포함할 클러스터당 기사 수


async def build_article_clusters(
    db: AsyncSession,
    period: str = "24h",
    min_cluster_size: int = 2,
) -> ArticleTrendsResponse:
    """
    기간 내 크롤링된 기사를 벡터 유사도로 클러스터링하여 트렌딩 토픽 반환

    Algorithm:
    1. DB에서 임베딩 완료 기사 조회
    2. Qdrant에서 벡터 일괄 조회
    3. 최신 기사부터 greedy 클러스터링 (threshold ≥ 0.75)
    4. 클러스터 메타데이터 계산
    5. article_count DESC 정렬
    """
    hours_map = {"24h": 24, "7d": 168, "30d": 720}
    hours = hours_map.get(period, 24)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # 1. DB에서 임베딩 완료 기사 조회
    category_col = Article.metadata_["category"].astext
    result = await db.execute(
        select(
            Article.id,
            Article.url,
            Article.title,
            Article.publisher,
            Article.published_at,
            Article.created_at,
            Article.qdrant_point_id,
            category_col.label("feed_category"),
        )
        .where(
            Article.qdrant_point_id.isnot(None),
            Article.created_at >= since,
        )
        .order_by(Article.created_at.desc())
        .limit(MAX_ARTICLES_FOR_CLUSTERING)
    )
    rows = result.all()

    if not rows:
        return _empty_response(period)

    # 기사 데이터 구조화
    articles_map = {}
    point_to_article = {}
    for row in rows:
        aid = str(row.id)
        pid = str(row.qdrant_point_id)
        articles_map[aid] = {
            "id": aid,
            "url": row.url,
            "title": row.title,
            "publisher": row.publisher,
            "published_at": row.published_at,
            "created_at": row.created_at,
            "qdrant_point_id": pid,
            "category": row.feed_category,
        }
        point_to_article[pid] = aid

    # 2. Qdrant에서 벡터 일괄 조회
    point_ids = list(point_to_article.keys())
    vectors = retrieve_vectors(point_ids)

    # 벡터가 없는 기사 제외
    valid_articles = {
        aid: data for aid, data in articles_map.items()
        if data["qdrant_point_id"] in vectors
    }

    if not valid_articles:
        return _empty_response(period)

    # 3. Greedy 클러스터링
    clustered_ids: set[str] = set()
    clusters: list[dict] = []

    # 최신 기사부터 순회
    sorted_articles = sorted(
        valid_articles.values(),
        key=lambda a: a["created_at"],
        reverse=True,
    )

    for article in sorted_articles:
        aid = article["id"]
        if aid in clustered_ids:
            continue

        pid = article["qdrant_point_id"]
        vector = vectors.get(pid)
        if not vector:
            continue

        # Qdrant에서 유사 기사 검색
        similar = search_similar(
            embedding=vector,
            limit=100,
            score_threshold=CLUSTER_SIMILARITY_THRESHOLD,
        )

        # 클러스터 멤버 수집
        members = [{"article": article, "score": 1.0}]
        clustered_ids.add(aid)

        for hit in similar:
            hit_aid = hit["payload"].get("article_id")
            if not hit_aid or hit_aid in clustered_ids:
                continue
            if hit_aid not in valid_articles:
                continue

            members.append({
                "article": valid_articles[hit_aid],
                "score": hit["score"],
            })
            clustered_ids.add(hit_aid)

        # 최소 크기 미달 시 싱글톤으로 처리 (나중에 필터링)
        cluster_id = str(uuid.uuid4())
        clusters.append({
            "cluster_id": cluster_id,
            "members": members,
        })

    # 4. 클러스터 메타데이터 계산
    topic_clusters = []
    for cluster in clusters:
        members = cluster["members"]
        if len(members) < min_cluster_size:
            continue

        articles_data = [m["article"] for m in members]
        scores = [m["score"] for m in members]

        publishers = list({a["publisher"] for a in articles_data if a["publisher"]})
        # 카테고리를 빈도순으로 정렬 (가장 많은 카테고리가 primary)
        cat_counts = Counter(a["category"] for a in articles_data if a["category"])
        categories = [cat for cat, _ in cat_counts.most_common()]

        timestamps = [
            a["published_at"] or a["created_at"]
            for a in articles_data
        ]
        first_seen = min(timestamps)
        last_seen = max(timestamps)

        # Growth rate: 기사 수 / 경과 시간
        duration_hours = max(
            (last_seen - first_seen).total_seconds() / 3600, 1.0
        )
        growth_rate = round(len(members) / duration_hours, 2)

        # 대표 기사 = 최신 기사 (첫 번째 멤버)
        rep = articles_data[0]

        # 클러스터 기사 목록 (시간순)
        sorted_members = sorted(
            members,
            key=lambda m: m["article"]["published_at"] or m["article"]["created_at"],
            reverse=True,
        )

        cluster_articles = [
            ClusterArticle(
                id=m["article"]["id"],
                title=m["article"]["title"],
                publisher=m["article"]["publisher"],
                published_at=m["article"]["published_at"],
                created_at=m["article"]["created_at"],
                url=m["article"]["url"],
                category=m["article"]["category"],
                similarity_score=round(m["score"], 3),
            )
            for m in sorted_members[:MAX_ARTICLES_PER_CLUSTER_RESPONSE]
        ]

        topic_clusters.append(TopicCluster(
            cluster_id=cluster["cluster_id"],
            title=rep["title"],
            article_count=len(members),
            publishers=publishers,
            categories=categories,
            first_seen=first_seen,
            last_seen=last_seen,
            avg_similarity=round(sum(scores) / len(scores), 3),
            representative_article=cluster_articles[0],
            articles=cluster_articles,
            growth_rate=growth_rate,
        ))

    # 5. 카테고리별 최소 1개 보장 + article_count DESC 정렬
    topic_clusters.sort(key=lambda c: c.article_count, reverse=True)

    # 각 카테고리에서 최소 1개 대표 클러스터 선택
    category_top: dict[str, TopicCluster] = {}
    remaining: list[TopicCluster] = []
    for tc in topic_clusters:
        primary_cat = tc.categories[0] if tc.categories else None
        if primary_cat and primary_cat not in category_top:
            category_top[primary_cat] = tc
        else:
            remaining.append(tc)

    # 카테고리 대표 + 나머지를 article_count 순으로 채움
    selected = list(category_top.values())
    slots_left = MAX_CLUSTERS - len(selected)
    selected.extend(remaining[:slots_left])
    selected.sort(key=lambda c: c.article_count, reverse=True)
    topic_clusters = selected

    # 6. 전체 분포 계산
    all_articles = list(valid_articles.values())
    category_dist = dict(Counter(
        a["category"] for a in all_articles if a["category"]
    ))

    # 6.5 카테고리에 기사가 있지만 클러스터가 없는 경우, 대표 기사로 싱글톤 클러스터 생성
    represented_cats = {tc.categories[0] for tc in topic_clusters if tc.categories}
    for cat, count in category_dist.items():
        if cat in represented_cats or count == 0:
            continue
        # 해당 카테고리의 최신 기사로 싱글톤 클러스터 생성
        cat_articles = [a for a in sorted_articles if a["category"] == cat]
        if not cat_articles:
            continue
        rep = cat_articles[0]
        ts = rep["published_at"] or rep["created_at"]
        cluster_article = ClusterArticle(
            id=rep["id"], title=rep["title"], publisher=rep["publisher"],
            published_at=rep["published_at"], created_at=rep["created_at"],
            url=rep["url"], category=rep["category"], similarity_score=1.0,
        )
        topic_clusters.append(TopicCluster(
            cluster_id=str(uuid.uuid4()), title=rep["title"],
            article_count=1,
            publishers=[rep["publisher"]] if rep["publisher"] else [],
            categories=[cat], first_seen=ts, last_seen=ts,
            avg_similarity=1.0, representative_article=cluster_article,
            articles=[cluster_article], growth_rate=0,
        ))
    publisher_dist = dict(Counter(
        a["publisher"] for a in all_articles if a["publisher"]
    ).most_common(20))

    # 시간대별 기사 수
    hourly = _compute_hourly_counts(all_articles, hours)

    return ArticleTrendsResponse(
        clusters=topic_clusters,
        total_articles=len(all_articles),
        total_clusters=len(topic_clusters),
        period=period,
        generated_at=datetime.now(timezone.utc),
        category_distribution=category_dist,
        publisher_distribution=publisher_dist,
        hourly_counts=hourly,
    )


def _compute_hourly_counts(articles: list[dict], total_hours: int) -> list[dict]:
    """시간대별 기사 수 집계"""
    now = datetime.now(timezone.utc)

    # 시간대별 집계 간격 결정
    if total_hours <= 24:
        interval_hours = 1
    elif total_hours <= 168:
        interval_hours = 6
    else:
        interval_hours = 24

    counts: dict[str, int] = {}
    for a in articles:
        ts = a["published_at"] or a["created_at"]
        # 간격에 맞게 반올림
        truncated = ts.replace(
            hour=(ts.hour // interval_hours) * interval_hours,
            minute=0, second=0, microsecond=0,
        )
        key = truncated.isoformat()
        counts[key] = counts.get(key, 0) + 1

    # 정렬된 리스트 반환
    return [
        {"hour": k, "count": v}
        for k, v in sorted(counts.items())
    ]


def _empty_response(period: str) -> ArticleTrendsResponse:
    """빈 응답 생성"""
    return ArticleTrendsResponse(
        clusters=[],
        total_articles=0,
        total_clusters=0,
        period=period,
        generated_at=datetime.now(timezone.utc),
    )
