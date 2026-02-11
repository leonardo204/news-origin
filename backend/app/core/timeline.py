"""
# timeline.py - Timeline Construction Logic
# Version: 0.1.0
# Description: 유사 기사들로부터 타임라인 구성, 전파 방향 추론
# Changes:
#   - 0.1.0: 시간순 정렬, 전파 추론, lifecycle 단계 판정
"""

from __future__ import annotations
from datetime import datetime, timedelta

from app.config import get_settings
from app.core.detector import detect_explosion_points

settings = get_settings()


def build_timeline(
    origin_article: dict,
    similar_articles: list[dict],
) -> list[dict]:
    """
    타임라인 구성

    [BUSINESS LOGIC - DO NOT MODIFY]
    1. 시간순 정렬 (published_at 기준)
    2. 전파 방향 추론: 시간이 빠른 유사 기사가 부모
    3. Lifecycle 단계 자동 판정

    Args:
        origin_article: 원본 기사 {id, title, published_at, ...}
        similar_articles: 유사 기사 목록 [{id, score, category, published_at, ...}]

    Returns:
        타임라인 엔트리 목록 [{article_id, similarity_score, category, lifecycle_stage, parent_id, is_origin}]
    """
    entries = []

    # 원본 기사 엔트리
    entries.append({
        "article_id": origin_article["id"],
        "similarity_score": 1.0,
        "similarity_category": "same",
        "lifecycle_stage": "origin",
        "parent_article_id": None,
        "is_origin": True,
    })

    # 유사 기사들을 시간순 정렬
    sorted_articles = sorted(
        similar_articles,
        key=lambda a: a.get("published_at") or datetime.max,
    )

    # 폭발 시점 감지
    all_times = [origin_article.get("published_at")]
    all_times.extend(a.get("published_at") for a in sorted_articles)
    valid_times = [t for t in all_times if t]
    explosion_ranges = detect_explosion_points(valid_times, len(sorted_articles) + 1)

    # 각 기사의 lifecycle 단계 판정 및 전파 부모 추론
    for article in sorted_articles:
        category = article.get("category", "isolated")

        # Lifecycle 단계 판정
        stage = _determine_lifecycle_stage(
            article.get("published_at"),
            origin_article.get("published_at"),
            explosion_ranges,
            category,
            len(entries),
        )

        # 전파 부모 추론: 시간이 가장 가까운 이전 기사 중 유사도 높은 것
        parent_id = _infer_parent(
            article, entries, origin_article["id"], category
        )

        entries.append({
            "article_id": article["id"],
            "similarity_score": article.get("score", 0.0),
            "similarity_category": category,
            "lifecycle_stage": stage,
            "parent_article_id": parent_id,
            "is_origin": False,
        })

    return entries


def _determine_lifecycle_stage(
    published_at: datetime | None,
    origin_time: datetime | None,
    explosion_ranges: list[tuple[datetime, datetime]],
    category: str,
    entry_index: int,
) -> str:
    """
    Lifecycle 단계 판정

    [BUSINESS LOGIC]
    - origin: 최초 기사 (index 0)
    - spread: origin 이후 2~5번째 기사
    - explosion: 폭발 시점 범위 내 기사
    - sustained: 폭발 이후 꾸준한 보도
    - fadeout: 마지막 구간 기사
    - isolated: 유사도 낮은 독립 기사
    """
    if category == "isolated":
        return "isolated"

    if not published_at or not origin_time:
        return "spread"

    # 폭발 시점 체크
    for exp_start, exp_end in explosion_ranges:
        if exp_start <= published_at <= exp_end:
            return "explosion"

    # Spread: 초기 5건 이내
    if entry_index <= 5:
        return "spread"

    # 시간 기반 판정
    elapsed = (published_at - origin_time).total_seconds() / 3600  # 시간

    if elapsed < 6:
        return "spread"
    elif elapsed < 48:
        return "sustained"
    else:
        return "fadeout"


def _infer_parent(
    article: dict,
    existing_entries: list[dict],
    origin_id: str,
    category: str,
) -> str | None:
    """
    전파 부모 추론

    [BUSINESS LOGIC]
    - isolated 기사: 부모 없음
    - same/derivative: 원본 기사가 부모
    - related: 시간순으로 가장 가까운 이전 기사가 부모
    """
    if category == "isolated":
        return None

    if category in ("same", "derivative"):
        return origin_id

    # related: 가장 최근 엔트리가 부모
    if existing_entries:
        return existing_entries[-1]["article_id"]

    return origin_id
