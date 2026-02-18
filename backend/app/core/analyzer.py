"""
# analyzer.py - Article Similarity Analyzer
# Version: 0.1.0
# Description: 기사 간 유사도 분석, 카테고리 분류
# Changes:
#   - 0.1.0: 임베딩 기반 유사도 분석, 카테고리 분류
"""

from app.config import get_settings
from app.services.embedding import create_embedding, get_article_text
from app.services.vector_store import search_similar, upsert_embedding
from typing import Optional

settings = get_settings()


def classify_similarity(score: float) -> str:
    """
    유사도 점수를 카테고리로 분류

    [BUSINESS LOGIC - DO NOT MODIFY]
    임계값 변경 시 config.py의 설정값을 수정할 것
    """
    if score >= settings.similarity_same_threshold:
        return "same"
    elif score >= settings.similarity_derivative_threshold:
        return "derivative"
    elif score >= settings.similarity_related_threshold:
        return "related"
    else:
        return "isolated"


def analyze_article(
    article_id: str,
    title: str,
    content: Optional[str] = None,
    publisher: Optional[str] = None,
    published_at: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> tuple[str, list[float]]:
    """
    기사 분석: 임베딩 생성 → Qdrant 저장

    Returns: (qdrant_point_id, embedding)
    """
    text = get_article_text(title)
    embedding = create_embedding(text)

    # Qdrant에 저장 (NER 키워드 포함)
    payload = {
        "title": title,
        "publisher": publisher,
        "published_at": published_at,
        "keywords": keywords or [],
    }
    point_id = upsert_embedding(article_id, embedding, payload)

    return point_id, embedding


def find_similar_articles(
    embedding: list[float],
    exclude_article_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    유사 기사 검색 (Qdrant 벡터 검색)

    Returns: [{id, score, payload, category}, ...]
    """
    results = search_similar(
        embedding=embedding,
        limit=limit + 1,  # 자기 자신 제외 가능성
        score_threshold=settings.similarity_related_threshold,
    )

    # 자기 자신 제외
    if exclude_article_id:
        results = [
            r for r in results
            if r["payload"].get("article_id") != exclude_article_id
        ]

    # 카테고리 분류 추가
    for r in results:
        r["category"] = classify_similarity(r["score"])

    return results[:limit]
