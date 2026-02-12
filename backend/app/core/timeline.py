"""
# timeline.py - Timeline Construction Logic
# Version: 0.2.0
# Description: 유사 기사들로부터 타임라인 구성, 진짜 기원점 탐지, 전파 방향 추론
# Changes:
#   - 0.1.0: 시간순 정렬, 전파 추론, lifecycle 단계 판정
#   - 0.2.0: 진짜 기원점 탐지 (가장 이른 same/derivative 기사)
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.core.detector import detect_explosion_points

settings = get_settings()


def build_timeline(
    input_article: dict,
    similar_articles: list[dict],
) -> tuple[list[dict], str]:
    """
    타임라인 구성 + 진짜 기원점 탐지

    1. 입력 기사 + same/derivative 유사 기사 중 가장 이른 기사를 기원으로 결정
    2. 시간순 정렬 (published_at 기준)
    3. 전파 방향 추론: 시간이 빠른 유사 기사가 부모
    4. Lifecycle 단계 자동 판정

    Args:
        input_article: 사용자 입력 기사 {id, title, published_at, ...}
        similar_articles: 유사 기사 목록 [{id, score, category, published_at, ...}]

    Returns:
        (타임라인 엔트리 목록, 진짜 기원 article_id)
    """
    # 진짜 기원 탐지
    true_origin, remaining = _find_true_origin(input_article, similar_articles)
    true_origin_id = true_origin["id"]

    entries = []

    # 기원 기사 엔트리
    entries.append({
        "article_id": true_origin_id,
        "similarity_score": 1.0,
        "similarity_category": "same",
        "lifecycle_stage": "origin",
        "parent_article_id": None,
        "is_origin": True,
    })

    # 유사 기사들을 시간순 정렬
    sorted_articles = sorted(
        remaining,
        key=lambda a: a.get("published_at") or datetime.max.replace(tzinfo=timezone.utc),
    )

    # 폭발 시점 감지
    all_times = [true_origin.get("published_at")]
    all_times.extend(a.get("published_at") for a in sorted_articles)
    valid_times = [t for t in all_times if t]
    explosion_ranges = detect_explosion_points(valid_times, len(sorted_articles) + 1)

    # 각 기사의 lifecycle 단계 판정 및 전파 부모 추론
    for article in sorted_articles:
        category = article.get("category", "isolated")

        # 유사도 50% 미만 (isolated) 기사는 타임라인에서 제외
        if category == "isolated":
            continue

        # Lifecycle 단계 판정
        stage = _determine_lifecycle_stage(
            article.get("published_at"),
            true_origin.get("published_at"),
            explosion_ranges,
            category,
            len(entries),
        )

        # 전파 부모 추론
        parent_id = _infer_parent(
            article, entries, true_origin_id, category
        )

        entries.append({
            "article_id": article["id"],
            "similarity_score": article.get("score", 0.0),
            "similarity_category": category,
            "lifecycle_stage": stage,
            "parent_article_id": parent_id,
            "is_origin": False,
        })

    return entries, true_origin_id


def _find_true_origin(
    input_article: dict,
    similar_articles: list[dict],
) -> tuple[dict, list[dict]]:
    """
    진짜 기원점 탐지

    입력 기사 + same/derivative 유사 기사 중 published_at이 가장 이른 기사를 기원으로 선택.
    기원이 입력 기사가 아닌 경우, 입력 기사를 나머지 목록에 추가.

    Returns:
        (진짜 기원 dict, 나머지 기사 목록)
    """
    input_id = input_article["id"]
    input_time = input_article.get("published_at")

    # 기원 후보: 입력 기사 + same/derivative 유사 기사 (published_at 필수)
    candidates = []
    if input_time:
        candidates.append({"time": input_time, "id": input_id, "score": 1.0})

    for a in similar_articles:
        cat = a.get("category", "isolated")
        if cat in ("same", "derivative") and a.get("published_at"):
            candidates.append({
                "time": a["published_at"],
                "id": a["id"],
                "score": a.get("score", 0.0),
            })

    if not candidates:
        # 시간 정보 없음 → 입력 기사가 기원 (fallback)
        return input_article, list(similar_articles)

    # 시간순 정렬, 동일 시간이면 유사도 높은 것 우선
    candidates.sort(key=lambda c: (c["time"], -c["score"]))
    true_origin_id = candidates[0]["id"]

    if true_origin_id == input_id:
        # 입력 기사가 가장 이름 → 기존 동작
        return input_article, list(similar_articles)

    # 진짜 기원은 유사 기사 중 하나
    true_origin_article = None
    remaining = []
    for a in similar_articles:
        if a["id"] == true_origin_id and true_origin_article is None:
            true_origin_article = a
        else:
            remaining.append(a)

    # 입력 기사를 나머지 목록에 추가 (score는 기원과의 대칭 유사도)
    remaining.append({
        **input_article,
        "score": true_origin_article.get("score", 1.0),
        "category": "same",
    })

    return true_origin_article, remaining


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
