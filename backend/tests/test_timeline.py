"""Timeline API route tests"""
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


async def test_tracking_status_not_found(client, mock_db):
    """존재하지 않는 추적 상태 조회 시 404"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/timeline/{uuid.uuid4()}/status")
    assert response.status_code == 404


async def test_tracking_status_processing(client, mock_db):
    """처리 중 추적 상태 조회"""
    tracking_id = uuid.uuid4()
    mock_tracking = MagicMock()
    mock_tracking.id = tracking_id
    mock_tracking.status = "processing"
    mock_tracking.progress = 45
    mock_tracking.total_articles = 3
    mock_tracking.error_message = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tracking
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/timeline/{tracking_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["progress"] == 45
    assert data["total_articles"] == 3


async def test_tracking_status_completed(client, mock_db):
    """완료된 추적 상태 조회"""
    tracking_id = uuid.uuid4()
    mock_tracking = MagicMock()
    mock_tracking.id = tracking_id
    mock_tracking.status = "completed"
    mock_tracking.progress = 100
    mock_tracking.total_articles = 10
    mock_tracking.error_message = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tracking
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/timeline/{tracking_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["progress"] == 100


@patch("app.api.routes.timeline.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.timeline.cache_set", new_callable=AsyncMock)
async def test_timeline_not_found(mock_cache_set, mock_cache_get, client, mock_db):
    """존재하지 않는 타임라인 조회 시 404"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/timeline/{uuid.uuid4()}")
    assert response.status_code == 404


@patch("app.api.routes.timeline.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.timeline.cache_set", new_callable=AsyncMock)
async def test_timeline_still_processing(mock_cache_set, mock_cache_get, client, mock_db):
    """아직 처리 중인 타임라인 조회 시 202"""
    mock_tracking = MagicMock()
    mock_tracking.status = "processing"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tracking
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/timeline/{uuid.uuid4()}")
    assert response.status_code == 202


async def test_search_news(client, mock_db):
    """뉴스 검색 API"""
    with patch("app.services.news_search.search_news", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {"url": "https://example.com/1", "title": "뉴스 1", "publisher": "뉴스사"},
            {"url": "https://example.com/2", "title": "뉴스 2"},
        ]

        response = await client.get("/api/search/news?q=테스트")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "뉴스 1"


async def test_search_news_short_query(client, mock_db):
    """검색어 2글자 미만 시 422"""
    response = await client.get("/api/search/news?q=a")
    assert response.status_code == 422


async def test_tracking_status_error_with_message(client, mock_db):
    """에러 상태에서 error_message 반환"""
    tracking_id = uuid.uuid4()
    mock_tracking = MagicMock()
    mock_tracking.id = tracking_id
    mock_tracking.status = "error"
    mock_tracking.progress = 60
    mock_tracking.total_articles = 5
    mock_tracking.error_message = "분석 시간이 초과되었습니다."

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tracking
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/timeline/{tracking_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["message"] == "분석 시간이 초과되었습니다."
    assert data["progress"] == 60


async def test_search_news_service_failure(client, mock_db):
    """뉴스 검색 서비스 실패 시 502"""
    with patch("app.services.news_search.search_news", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = Exception("RSS feed unavailable")

        response = await client.get("/api/search/news?q=테스트뉴스")
        assert response.status_code == 502
