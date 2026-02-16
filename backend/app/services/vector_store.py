"""
# vector_store.py - Qdrant Vector Store Service
# Version: 0.1.0
# Description: Qdrant 벡터 DB 연동 - 임베딩 저장, 유사도 검색
# Changes:
#   - 0.1.0: Collection 관리, upsert, search 구현
"""

import uuid
from datetime import datetime
from typing import Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import get_settings

settings = get_settings()

_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """Qdrant 클라이언트 싱글톤"""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30,
        )
    return _client


async def ensure_collection():
    """
    Qdrant 컬렉션 존재 확인 및 생성

    [BUSINESS LOGIC]
    Cosine distance 사용 - Azure OpenAI text-embedding-3-large 임베딩에 최적
    1024 dimensions = text-embedding-3-large (dimensions=1024로 축소)
    차원 불일치 시 컬렉션 재생성 (마이그레이션 스크립트에서 처리)
    """
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    try:
        info = client.get_collection(collection_name)
        # 차원 불일치 확인
        current_dim = info.config.params.vectors.size
        if current_dim != settings.embedding_dimension:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Qdrant collection dimension mismatch: "
                f"current={current_dim}, expected={settings.embedding_dimension}. "
                f"Run migration script to recreate collection."
            )
    except (UnexpectedResponse, Exception):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=settings.embedding_dimension,
                distance=models.Distance.COSINE,
            ),
        )


def upsert_embedding(
    article_id: str,
    embedding: list[float],
    payload: Optional[dict] = None,
) -> str:
    """
    기사 임베딩을 Qdrant에 저장

    Returns: Qdrant point ID (UUID)
    """
    client = get_qdrant_client()
    point_id = str(uuid.uuid4())

    point_payload = payload or {}
    point_payload["article_id"] = article_id

    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload=point_payload,
            )
        ],
    )

    return point_id


def retrieve_vectors(point_ids: list[str]) -> dict[str, list[float]]:
    """
    Qdrant에서 포인트 ID 목록으로 벡터 일괄 조회

    Returns: {point_id: vector, ...}
    """
    if not point_ids:
        return {}

    client = get_qdrant_client()
    result = {}

    # Qdrant retrieve는 배치 크기 제한이 있으므로 100개씩 분할
    batch_size = 100
    for i in range(0, len(point_ids), batch_size):
        batch = point_ids[i:i + batch_size]
        points = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=batch,
            with_vectors=True,
        )
        for point in points:
            result[str(point.id)] = point.vector

    return result


def search_similar(
    embedding: list[float],
    limit: int = 50,
    score_threshold: float = 0.5,
    filter_conditions: Optional[dict] = None,
) -> list[dict]:
    """
    유사 기사 벡터 검색

    Args:
        embedding: 쿼리 벡터 (1024-dim, text-embedding-3-large)
        limit: 최대 결과 수
        score_threshold: 최소 유사도 점수
        filter_conditions: Qdrant 필터 조건

    Returns: [{id, score, payload}, ...]
    """
    client = get_qdrant_client()

    query_filter = None
    if filter_conditions:
        must_conditions = []
        for key, value in filter_conditions.items():
            must_conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
            )
        query_filter = models.Filter(must=must_conditions)

    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=embedding,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
    )

    return [
        {
            "id": str(hit.id),
            "score": hit.score,
            "payload": hit.payload,
        }
        for hit in response.points
    ]
