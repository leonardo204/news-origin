"""Trends API route tests"""
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


@patch("app.api.routes.trends.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.trends.cache_set", new_callable=AsyncMock)
async def test_hot_trends_empty(mock_cache_set, mock_cache_get, client, mock_db):
    """트렌드 없을 때 빈 리스트 반환"""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get("/api/trends/hot")
    assert response.status_code == 200
    assert response.json() == []


@patch("app.api.routes.trends.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.trends.cache_set", new_callable=AsyncMock)
async def test_hot_trends_with_data(mock_cache_set, mock_cache_get, client, mock_db):
    """트렌드 데이터 반환"""
    mock_row = MagicMock()
    mock_row.input_text = "테스트 뉴스"
    mock_row.cnt = 5
    mock_row.latest_id = str(uuid.uuid4())
    mock_row.latest = datetime(2024, 1, 15, tzinfo=timezone.utc)

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get("/api/trends/hot?period=24h")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "테스트 뉴스"
    assert data[0]["tracking_count"] == 5


@patch("app.api.routes.trends.cache_get", new_callable=AsyncMock)
async def test_hot_trends_cached(mock_cache_get, client, mock_db):
    """캐시 히트 시 DB 쿼리 없이 반환"""
    cached_data = [{"title": "캐시된 트렌드", "tracking_count": 10, "latest_tracking_id": None, "last_tracked_at": None}]
    mock_cache_get.return_value = cached_data

    response = await client.get("/api/trends/hot")
    assert response.status_code == 200
    # DB should not be called
    mock_db.execute.assert_not_called()


@patch("app.api.routes.trends.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.trends.cache_set", new_callable=AsyncMock)
async def test_stats_overview(mock_cache_set, mock_cache_get, client, mock_db):
    """통계 개요 반환"""
    # Three separate queries for tracking_count, article_count, active_count
    mock_result1 = MagicMock()
    mock_result1.scalar.return_value = 42
    mock_result2 = MagicMock()
    mock_result2.scalar.return_value = 150
    mock_result3 = MagicMock()
    mock_result3.scalar.return_value = 3

    mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2, mock_result3])

    response = await client.get("/api/trends/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_trackings"] == 42
    assert data["total_articles"] == 150
    assert data["active_trackings"] == 3


@patch("app.api.routes.trends.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.trends.cache_set", new_callable=AsyncMock)
async def test_popular_searches_empty(mock_cache_set, mock_cache_get, client, mock_db):
    """인기 검색어 없을 때 빈 리스트"""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.get("/api/trends/popular-searches")
    assert response.status_code == 200
    assert response.json() == []


async def test_hot_trends_invalid_period(client, mock_db):
    """잘못된 period 파라미터 시 422"""
    response = await client.get("/api/trends/hot?period=1y")
    assert response.status_code == 422


@patch("app.api.routes.trends.cache_get", new_callable=AsyncMock, return_value=None)
@patch("app.api.routes.trends.cache_set", new_callable=AsyncMock)
async def test_hot_trends_valid_periods(mock_cache_set, mock_cache_get, client, mock_db):
    """유효한 period 파라미터 (24h, 7d, 30d)"""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    for period in ["24h", "7d", "30d"]:
        response = await client.get(f"/api/trends/hot?period={period}")
        assert response.status_code == 200
