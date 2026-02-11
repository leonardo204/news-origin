"""Article API route tests"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_session


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
async def client(mock_db):
    async def override():
        yield mock_db

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_track_article_with_url(client, mock_db):
    """URL 입력 시 크롤링하여 기사 반환"""
    article_id = uuid.uuid4()
    mock_article = MagicMock()
    mock_article.id = article_id
    mock_article.url = "https://example.com/article"
    mock_article.title = "Test Article"
    mock_article.publisher = "Test News"
    mock_article.publisher_domain = "example.com"
    mock_article.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_article.author = None
    mock_article.summary = None
    mock_article.language = "ko"
    mock_article.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Mock crawl_article
    with patch("app.core.crawler.crawl_article", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "publisher": "Test News",
            "publisher_domain": "example.com",
        }

        # Mock DB select returning no existing article
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        # After flush, mock the article object that was added
        def capture_add(obj):
            obj.id = article_id
            obj.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            obj.language = "ko"
        mock_db.add = MagicMock(side_effect=capture_add)
        mock_db.flush = AsyncMock()

        response = await client.post(
            "/api/articles/track",
            json={"text": "https://example.com/article"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "url"


async def test_track_article_with_title(client, mock_db):
    """제목 입력 시 검색 결과 반환"""
    with patch("app.services.news_search.search_news", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {
                "title": "뉴스 기사 1",
                "url": "https://example.com/1",
                "publisher": "뉴스사",
                "published_at": "2024-01-15T10:00:00Z",
            },
            {
                "title": "뉴스 기사 2",
                "url": "https://example.com/2",
                "publisher": "뉴스사2",
            },
        ]

        response = await client.post(
            "/api/articles/track",
            json={"text": "뉴스 기사 제목 검색"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "title"
    assert len(data["candidates"]) == 2
    assert data["candidates"][0]["title"] == "뉴스 기사 1"


async def test_track_article_empty_text(client, mock_db):
    """빈 텍스트 입력 시 422 에러 (min_length=2)"""
    response = await client.post(
        "/api/articles/track",
        json={"text": ""},
    )
    assert response.status_code == 422


async def test_track_article_single_char(client, mock_db):
    """1글자 입력 시 422 에러 (min_length=2)"""
    response = await client.post(
        "/api/articles/track",
        json={"text": "a"},
    )
    assert response.status_code == 422


async def test_track_article_too_long(client, mock_db):
    """2000자 초과 시 422 에러 (max_length=2000)"""
    response = await client.post(
        "/api/articles/track",
        json={"text": "x" * 2001},
    )
    assert response.status_code == 422


async def test_track_article_crawl_failure(client, mock_db):
    """크롤링 실패 시 502 에러"""
    with patch("app.core.crawler.crawl_article", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.side_effect = Exception("Connection timeout")

        response = await client.post(
            "/api/articles/track",
            json={"text": "https://example.com/bad-article"},
        )

    assert response.status_code == 502


async def test_track_article_search_failure(client, mock_db):
    """뉴스 검색 서비스 실패 시 502 에러"""
    with patch("app.services.news_search.search_news", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = Exception("Service unavailable")

        response = await client.post(
            "/api/articles/track",
            json={"text": "뉴스 검색 제목"},
        )

    assert response.status_code == 502


async def test_confirm_article_not_found(client, mock_db):
    """존재하지 않는 기사 확인 시 404"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.post(
        "/api/articles/confirm",
        json={"article_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


async def test_confirm_article_success(client, mock_db):
    """기사 확인 성공 시 추적 시작"""
    article_id = uuid.uuid4()
    mock_article = MagicMock()
    mock_article.id = article_id
    mock_article.title = "Test Article"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_article
    mock_db.execute = AsyncMock(return_value=mock_result)

    tracking_id = uuid.uuid4()
    def capture_add(obj):
        obj.id = tracking_id

    mock_db.add = MagicMock(side_effect=capture_add)

    with patch("app.workers.tasks.analyze_article_propagation") as mock_task:
        mock_task.delay = MagicMock()

        response = await client.post(
            "/api/articles/confirm",
            json={"article_id": str(article_id)},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["tracking_id"] == str(tracking_id)


async def test_get_article_not_found(client, mock_db):
    """존재하지 않는 기사 조회 시 404"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/articles/{uuid.uuid4()}")
    assert response.status_code == 404
