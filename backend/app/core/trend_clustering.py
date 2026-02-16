"""
# trend_clustering.py - Article Trend Clustering Service
# Version: 0.4.0
# Description: 가중치 복합 스코어링 기반 기사 클러스터링으로 트렌딩 토픽 추출
# Changes:
#   - 0.1.0: Greedy 클러스터링 알고리즘, 메타데이터 계산
#   - 0.2.0: NER 키워드 + 임베딩 가중치 복합 스코어링 도입
#   - 0.3.0: 제목 중복 제거 + 유사 클러스터 자동 병합 (실효성 부족으로 0.4.0에서 교체)
#   - 0.4.0: 그래프 기반 클러스터 병합 (connected components)
#            임베딩 유사도 + 키워드 겹침 게이트, 전이적 병합으로 동일 토픽 통합
"""

import logging
import math
import uuid
from collections import Counter, deque
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
from app.services.keyword_extractor import compute_keyword_similarity

logger = logging.getLogger(__name__)

# 클러스터링 설정
CLUSTER_EMBEDDING_THRESHOLD = 0.50   # Qdrant 후보 검색 최소 임베딩 유사도
CLUSTER_FINAL_THRESHOLD = 0.45       # 최종 가중치 스코어 임계값
EMBEDDING_ONLY_THRESHOLD = 0.85      # 키워드 겹침 없을 때 임베딩만으로 통과 임계값
SAME_PUBLISHER_PENALTY = 0.05        # 같은 출판사 유사도 보정
ALPHA = 0.6                          # 임베딩 유사도 가중치
BETA = 0.4                           # 키워드 유사도 가중치
CLUSTER_MERGE_EMB_THRESHOLD = 0.52   # 클러스터 seed 간 임베딩 유사도 병합 임계값
MAX_COMPONENT_ARTICLES = 30          # 병합 시 component 최대 기사 수 (초과 시 확장 중단)
MAX_ARTICLES_FOR_CLUSTERING = 500
MAX_CLUSTERS = 20
MAX_ARTICLES_PER_CLUSTER_RESPONSE = 10


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """코사인 유사도 계산"""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_keyword_texts(keywords_data: dict) -> set[str]:
    """키워드 데이터에서 모든 키워드/엔터티 텍스트 추출"""
    texts = set(keywords_data.get("keywords", []))
    for e in keywords_data.get("entities", []):
        t = e.get("text", "")
        if t:
            texts.add(t)
    texts.discard("")
    return texts


def _has_keyword_overlap(kws_a: set[str], kws_b: set[str]) -> bool:
    """키워드 겹침 확인 (정확 일치 또는 부분 문자열 매칭)

    한국어 NER 특성상 "이재명"/"이 대표", "민주당"/"더불어민주당" 등
    동일 엔터티의 다양한 표현이 존재하므로 부분 문자열 매칭도 허용
    """
    if kws_a & kws_b:
        return True
    for a in kws_a:
        if len(a) < 2:
            continue
        for b in kws_b:
            if len(b) < 2:
                continue
            if a in b or b in a:
                return True
    return False


def _merge_similar_clusters(
    clusters: list[dict],
    vectors: dict[str, list[float]],
) -> list[dict]:
    """
    그래프 기반 클러스터 병합 (connected components)

    각 클러스터 seed 간 임베딩 유사도가 CLUSTER_MERGE_EMB_THRESHOLD 이상이고
    키워드가 1개 이상 겹치면 edge를 생성.
    BFS로 connected component를 찾아 전이적으로 병합.
    (예: A↔B, B↔C이면 A,B,C 모두 하나의 클러스터로 병합)
    """
    n = len(clusters)
    if n <= 1:
        return clusters

    # 각 클러스터 seed의 벡터와 키워드 사전 추출
    seed_vecs: list[list[float] | None] = []
    seed_kws: list[set[str]] = []
    for c in clusters:
        seed = c["members"][0]["article"]
        seed_vecs.append(vectors.get(seed["qdrant_point_id"]))
        seed_kws.append(_get_keyword_texts(seed.get("keywords_data", {})))

    # 인접 리스트 구축
    adj: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        if not seed_vecs[i]:
            continue
        for j in range(i + 1, n):
            if not seed_vecs[j]:
                continue
            emb_sim = _cosine_similarity(seed_vecs[i], seed_vecs[j])
            if emb_sim < CLUSTER_MERGE_EMB_THRESHOLD:
                continue
            # 키워드 겹침 게이트: 최소 1개 공통 키워드 필요 (부분 매칭 포함)
            if not _has_keyword_overlap(seed_kws[i], seed_kws[j]):
                continue
            adj[i].append(j)
            adj[j].append(i)

    # BFS로 connected components 탐색 (기사 수 제한 적용)
    visited = [False] * n
    cluster_sizes = [len(c["members"]) for c in clusters]
    components: list[list[int]] = []
    for i in range(n):
        if visited[i]:
            continue
        component: list[int] = []
        component_articles = cluster_sizes[i]  # 시작 노드 포함
        queue = deque([i])
        visited[i] = True
        while queue:
            node = queue.popleft()
            component.append(node)
            for neighbor in adj[node]:
                if not visited[neighbor]:
                    # 기사 수 제한: 추가 전에 초과 여부 확인
                    if component_articles + cluster_sizes[neighbor] > MAX_COMPONENT_ARTICLES:
                        continue
                    component_articles += cluster_sizes[neighbor]
                    visited[neighbor] = True
                    queue.append(neighbor)
        components.append(component)

    # 각 component의 클러스터들을 병합
    merged: list[dict] = []
    merge_count = 0
    for comp in components:
        if len(comp) == 1:
            merged.append(clusters[comp[0]])
            continue

        merge_count += len(comp) - 1
        base = clusters[comp[0]]
        all_members = list(base["members"])
        seen_ids = {m["article"]["id"] for m in all_members}
        for idx in comp[1:]:
            for m in clusters[idx]["members"]:
                if m["article"]["id"] not in seen_ids:
                    all_members.append(m)
                    seen_ids.add(m["article"]["id"])
        merged.append({
            "cluster_id": base["cluster_id"],
            "members": all_members,
        })

    if merge_count > 0:
        logger.info(f"Cluster merge: {n} → {len(merged)} ({merge_count} merged)")
    return merged


async def build_article_clusters(
    db: AsyncSession,
    period: str = "24h",
    min_cluster_size: int = 2,
) -> ArticleTrendsResponse:
    """
    기간 내 크롤링된 기사를 가중치 복합 스코어링으로 클러스터링하여 트렌딩 토픽 반환

    Algorithm:
    1. DB에서 임베딩 완료 기사 + NER 키워드 조회
    2. Qdrant에서 벡터 일괄 조회
    3. 최신 기사부터 greedy 클러스터링 (가중치 스코어)
       final_score = α × cosine_sim + β × keyword_sim
    4. 클러스터 메타데이터 계산
    5. article_count DESC 정렬
    """
    hours_map = {"24h": 24, "7d": 168, "30d": 720}
    hours = hours_map.get(period, 24)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # 1. DB에서 임베딩 완료 기사 + 메타데이터(키워드 포함) 조회
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
            Article.metadata_,
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

    # 기사 데이터 구조화 (NER 키워드 포함)
    articles_map = {}
    point_to_article = {}
    for row in rows:
        aid = str(row.id)
        pid = str(row.qdrant_point_id)
        meta = row.metadata_ or {}
        articles_map[aid] = {
            "id": aid,
            "url": row.url,
            "title": row.title,
            "publisher": row.publisher,
            "published_at": row.published_at,
            "created_at": row.created_at,
            "qdrant_point_id": pid,
            "category": row.feed_category,
            "keywords_data": meta.get("keywords_data", {}),
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

    # 3. Greedy 클러스터링 (가중치 복합 스코어링)
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

        # Qdrant에서 유사 기사 검색 (낮은 임계값으로 넓게 후보 수집)
        similar = search_similar(
            embedding=vector,
            limit=100,
            score_threshold=CLUSTER_EMBEDDING_THRESHOLD,
        )

        # 클러스터 멤버 수집 (가중치 복합 스코어링)
        members = [{"article": article, "score": 1.0}]
        clustered_ids.add(aid)
        seed_publisher = article.get("publisher", "")
        seed_keywords = article.get("keywords_data", {})

        for hit in similar:
            hit_aid = hit["payload"].get("article_id")
            if not hit_aid or hit_aid in clustered_ids:
                continue
            if hit_aid not in valid_articles:
                continue

            embedding_score = hit["score"]
            hit_article = valid_articles[hit_aid]

            # 같은 출판사 임베딩 유사도 보정
            if seed_publisher and hit_article.get("publisher") == seed_publisher:
                embedding_score -= SAME_PUBLISHER_PENALTY

            if embedding_score < CLUSTER_EMBEDDING_THRESHOLD:
                continue

            # NER 키워드 유사도 계산
            hit_keywords = hit_article.get("keywords_data", {})
            keyword_score = compute_keyword_similarity(seed_keywords, hit_keywords)

            # 가중치 복합 스코어
            final_score = ALPHA * embedding_score + BETA * keyword_score

            # 게이트 로직:
            # 1. 키워드 겹침이 없으면 매우 높은 임베딩 유사도 필요
            # 2. 키워드 겹침이 있으면 가중치 스코어 임계값 적용
            if keyword_score == 0:
                if embedding_score < EMBEDDING_ONLY_THRESHOLD:
                    continue
                # 키워드 없이 높은 임베딩만으로 통과 (final_score = embedding만)
                final_score = embedding_score
            elif final_score < CLUSTER_FINAL_THRESHOLD:
                continue

            members.append({
                "article": hit_article,
                "score": round(final_score, 4),
            })
            clustered_ids.add(hit_aid)

        cluster_id = str(uuid.uuid4())
        clusters.append({
            "cluster_id": cluster_id,
            "members": members,
        })

    # 3.5. 유사 클러스터 병합 (seed 간 유사도 기반)
    clusters = _merge_similar_clusters(clusters, vectors)

    # 4. 클러스터 메타데이터 계산
    topic_clusters = []
    for cluster in clusters:
        members = cluster["members"]
        if len(members) < min_cluster_size:
            continue

        articles_data = [m["article"] for m in members]
        scores = [m["score"] for m in members]

        publishers = list({a["publisher"] for a in articles_data if a["publisher"]})
        cat_counts = Counter(a["category"] for a in articles_data if a["category"])
        categories = [cat for cat, _ in cat_counts.most_common()]

        timestamps = [
            a["published_at"] or a["created_at"]
            for a in articles_data
        ]
        first_seen = min(timestamps)
        last_seen = max(timestamps)

        duration_hours = max(
            (last_seen - first_seen).total_seconds() / 3600, 1.0
        )
        growth_rate = round(len(members) / duration_hours, 2)

        rep = articles_data[0]

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

    category_top: dict[str, TopicCluster] = {}
    remaining: list[TopicCluster] = []
    for tc in topic_clusters:
        primary_cat = tc.categories[0] if tc.categories else None
        if primary_cat and primary_cat not in category_top:
            category_top[primary_cat] = tc
        else:
            remaining.append(tc)

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

    if total_hours <= 24:
        interval_hours = 1
    elif total_hours <= 168:
        interval_hours = 6
    else:
        interval_hours = 24

    counts: dict[str, int] = {}
    for a in articles:
        ts = a["published_at"] or a["created_at"]
        truncated = ts.replace(
            hour=(ts.hour // interval_hours) * interval_hours,
            minute=0, second=0, microsecond=0,
        )
        key = truncated.isoformat()
        counts[key] = counts.get(key, 0) + 1

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
