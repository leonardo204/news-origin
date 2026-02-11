"""Test configuration and fixtures

Note: This project requires Python 3.10+ due to PEP 604 type union syntax (str | None).
If running on Python 3.9, the models need to add: from __future__ import annotations
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Disable rate limiter for all tests."""
    from app.core.limiter import limiter
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_article_data():
    """Sample article data dict"""
    return {
        "id": uuid.uuid4(),
        "url": "https://example.com/news/test-article",
        "title": "테스트 뉴스 기사 제목",
        "content": "뉴스 기사 본문 내용입니다.",
        "publisher": "테스트 뉴스",
        "publisher_domain": "example.com",
        "published_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        "language": "ko",
        "created_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_tracking_data(sample_article_data):
    """Sample tracking request data"""
    return {
        "id": uuid.uuid4(),
        "input_text": "테스트 뉴스",
        "input_type": "title",
        "origin_article_id": sample_article_data["id"],
        "status": "completed",
        "total_articles": 5,
        "progress": 100,
        "created_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def mock_db_session():
    """Mock async database session"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session
