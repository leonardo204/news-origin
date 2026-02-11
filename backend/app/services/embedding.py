"""
# embedding.py - Embedding Service
# Version: 0.1.0
# Description: sentence-transformers 기반 텍스트 임베딩 생성
# Changes:
#   - 0.1.0: 모델 로딩, 단일/배치 임베딩 생성
"""

from functools import lru_cache
from typing import Optional

from app.config import get_settings

settings = get_settings()

_model = None


def get_model():
    """
    sentence-transformers 모델 싱글톤 로딩

    [BUSINESS LOGIC - DO NOT MODIFY]
    모델은 최초 1회만 로딩하며 이후 재사용
    paraphrase-multilingual-mpnet-base-v2: 다국어 지원 (한국어 포함)
    출력 차원: 768
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    return _model


def create_embedding(text: str) -> list[float]:
    """단일 텍스트 임베딩 생성"""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    배치 텍스트 임베딩 생성

    [CRITICAL] 대량 기사 처리 시 반드시 배치 사용
    개별 호출 대비 5-10x 성능 향상
    """
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


def get_article_text(title: str, content: Optional[str] = None) -> str:
    """
    기사 임베딩용 텍스트 구성

    [BUSINESS LOGIC]
    제목 + 본문 앞 500자를 결합하여 임베딩 입력으로 사용
    제목만으로는 유사도 판별이 부정확할 수 있음
    """
    text = title
    if content:
        # 본문 앞 500자만 사용 (성능 + 핵심 정보 집중)
        text += " " + content[:500]
    return text
