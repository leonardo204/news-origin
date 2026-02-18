"""
# embedding.py - Embedding Service
# Version: 0.2.0
# Description: Azure OpenAI text-embedding-3-large 기반 텍스트 임베딩 생성
# Changes:
#   - 0.1.0: sentence-transformers 기반 로컬 임베딩
#   - 0.2.0: Azure OpenAI API로 교체 (text-embedding-3-large, 1024차원)
#            로컬 모델 제거 → 메모리 ~1GB 절감
"""

from app.config import get_settings
from app.services.azure_openai import create_embedding_sync, create_embeddings_batch_sync

settings = get_settings()


def create_embedding(text: str) -> list[float]:
    """단일 텍스트 임베딩 생성 (Azure OpenAI API)"""
    return create_embedding_sync(text)


def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    배치 텍스트 임베딩 생성 (Azure OpenAI API)

    [CRITICAL] 대량 기사 처리 시 반드시 배치 사용
    API 호출 횟수 최소화 (16개씩 배치 전송)
    """
    return create_embeddings_batch_sync(texts)


def get_article_text(title: str) -> str:
    """
    기사 임베딩용 텍스트 구성

    [BUSINESS LOGIC]
    제목만 사용하여 토픽 시그널 극대화
    본문 보일러플레이트(네비게이션, 광고, 쿠키 등)로 인한 유사도 과대평가 완전 제거
    """
    return title
