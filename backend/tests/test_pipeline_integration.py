"""
Integration tests for the Celery article analysis pipeline.

Tests the complete analyze_article_propagation flow with all external dependencies mocked.
Uses late imports as in the actual tasks.py implementation.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.tasks import _run_pipeline, _mark_failed


@pytest.fixture
def tracking_id():
    """Generate a unique tracking ID."""
    return str(uuid.uuid4())


@pytest.fixture
def article_id():
    """Generate a unique article ID."""
    return str(uuid.uuid4())


@pytest.fixture
def origin_article(article_id):
    """Create a mock origin article with proper string attributes."""
    # Create a simple object instead of MagicMock to avoid attribute masking
    class MockArticle:
        def __init__(self):
            self.id = uuid.UUID(article_id)
            self.title = "원본 기사: AI 기술 발전"
            self.content = "인공지능 기술이 빠르게 발전하고 있습니다. " * 20
            self.url = "https://example.com/origin-article"
            self.publisher = "예제신문"
            self.published_at = datetime(2024, 1, 1, 12, 0, 0)
            self.qdrant_point_id = None

    return MockArticle()


@pytest.fixture
def tracking_request(tracking_id, article_id):
    """Create a mock tracking request."""
    mock_tracking = MagicMock()
    mock_tracking.id = uuid.UUID(tracking_id)
    mock_tracking.input_text = "https://example.com/origin-article"
    mock_tracking.input_type = "url"
    mock_tracking.origin_article_id = uuid.UUID(article_id)
    mock_tracking.status = "pending"
    mock_tracking.progress = 0
    mock_tracking.total_articles = 0
    mock_tracking.error_message = None
    mock_tracking.completed_at = None
    return mock_tracking


@pytest.fixture
def mock_db_session(tracking_request, origin_article):
    """Create a mock database session."""
    mock_session = AsyncMock()

    # Mock database query results - return tracking and origin objects consistently
    mock_result_tracking = AsyncMock()
    mock_result_tracking.scalar_one = Mock(return_value=tracking_request)
    mock_result_tracking.scalar_one_or_none = Mock(return_value=tracking_request)

    mock_result_origin = AsyncMock()
    mock_result_origin.scalar_one = Mock(return_value=origin_article)
    mock_result_origin.scalar_one_or_none = Mock(return_value=origin_article)

    mock_result_none = AsyncMock()
    mock_result_none.scalar_one_or_none = Mock(return_value=None)

    # Mock execute to return appropriate results based on call order
    # Pipeline call order:
    #   1: select(TrackingRequest) → tracking_request
    #   2: select(Article).where(id == ...) → origin_article
    #   3+: select(Article).where(url == ...) → None (for each crawled article)
    call_count = {"count": 0}

    async def mock_execute(query):
        call_count["count"] += 1
        c = call_count["count"]

        if c == 1:
            return mock_result_tracking
        elif c == 2:
            return mock_result_origin
        else:
            return mock_result_none

    mock_session.execute = AsyncMock(side_effect=mock_execute)
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()

    return mock_session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """Create a mock session factory."""
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_factory


@pytest.fixture
def mock_search_results():
    """Create mock Google News search results."""
    return [
        {
            "title": "유사 기사 1",
            "url": "https://example.com/article-1",
            "publisher": "뉴스1",
            "published_at": datetime(2024, 1, 1, 13, 0, 0),
        },
        {
            "title": "유사 기사 2",
            "url": "https://example.com/article-2",
            "publisher": "뉴스2",
            "published_at": datetime(2024, 1, 1, 14, 0, 0),
        },
        {
            "title": "유사 기사 3",
            "url": "https://example.com/article-3",
            "publisher": "뉴스3",
            "published_at": datetime(2024, 1, 1, 15, 0, 0),
        },
    ]


@pytest.fixture
def mock_crawled_articles():
    """Create mock crawled articles."""
    return [
        {
            "url": "https://example.com/article-1",
            "title": "유사 기사 1",
            "content": "AI 기술의 발전에 대한 내용입니다. " * 10,
            "publisher": "뉴스1",
            "published_at": datetime(2024, 1, 1, 13, 0, 0),
        },
        {
            "url": "https://example.com/article-2",
            "title": "유사 기사 2",
            "content": "인공지능 관련 뉴스입니다. " * 10,
            "publisher": "뉴스2",
            "published_at": datetime(2024, 1, 1, 14, 0, 0),
        },
    ]


@pytest.fixture
def mock_qdrant_results():
    """Create mock Qdrant similarity search results."""
    return [
        {
            "score": 0.92,
            "category": "same",
            "payload": {"article_id": "article-uuid-1"},
        },
        {
            "score": 0.78,
            "category": "derivative",
            "payload": {"article_id": "article-uuid-2"},
        },
    ]


@pytest.fixture
def mock_timeline_entries():
    """Create mock timeline entries."""
    return [
        {
            "article_id": "origin-uuid",
            "similarity_score": 1.0,
            "similarity_category": "origin",
            "lifecycle_stage": "origin",
            "is_origin": True,
        },
        {
            "article_id": "article-uuid-1",
            "similarity_score": 0.92,
            "similarity_category": "same",
            "lifecycle_stage": "spread",
            "parent_article_id": "origin-uuid",
            "is_origin": False,
        },
    ]


@pytest.mark.anyio
async def test_pipeline_happy_path(
    tracking_id,
    article_id,
    tracking_request,
    origin_article,
    mock_session_factory,
    mock_db_session,
    mock_search_results,
    mock_crawled_articles,
    mock_qdrant_results,
    mock_timeline_entries,
):
    """Test successful pipeline execution with all steps completing."""

    mock_task = MagicMock()

    with patch("app.models.base.async_session_factory", mock_session_factory), \
         patch("app.core.analyzer.analyze_article") as mock_analyze, \
         patch("app.core.analyzer.find_similar_articles") as mock_find_similar, \
         patch("app.services.news_search.search_news") as mock_search_news, \
         patch("app.core.crawler.crawl_articles_batch") as mock_crawl, \
         patch("app.core.timeline.build_timeline") as mock_build_timeline, \
         patch("app.services.cache.cache_delete") as mock_cache_delete:

        # Configure mocks
        mock_analyze.side_effect = [
            (str(uuid.uuid4()), [0.1] * 768),  # Origin article embedding
            (str(uuid.uuid4()), [0.11] * 768),  # Article 1 embedding
            (str(uuid.uuid4()), [0.12] * 768),  # Article 2 embedding
        ]

        mock_search_news.return_value = mock_search_results
        mock_crawl.return_value = mock_crawled_articles
        mock_find_similar.return_value = mock_qdrant_results
        mock_build_timeline.return_value = mock_timeline_entries

        # Run pipeline
        await _run_pipeline(mock_task, tracking_id, article_id)

        # Verify tracking status updates
        assert tracking_request.status == "completed"
        assert tracking_request.progress == 100
        assert tracking_request.completed_at is not None

        # Verify analyze_article was called for origin + crawled articles
        assert mock_analyze.call_count == 3

        # Verify search_news was called with origin title
        mock_search_news.assert_called_once()

        # Verify crawl_articles_batch was called
        mock_crawl.assert_called_once()

        # Verify find_similar_articles was called
        mock_find_similar.assert_called_once()

        # Verify build_timeline was called
        mock_build_timeline.assert_called_once()

        # Verify cache invalidation (5 cache keys)
        assert mock_cache_delete.call_count == 5


@pytest.mark.anyio
async def test_pipeline_handles_crawl_failure(
    tracking_id,
    article_id,
    tracking_request,
    origin_article,
    mock_session_factory,
    mock_db_session,
    mock_search_results,
    mock_timeline_entries,
):
    """Test pipeline continues when some URLs fail to crawl."""

    mock_task = MagicMock()

    # Only 1 article successfully crawled out of 3
    partial_crawled = [
        {
            "url": "https://example.com/article-1",
            "title": "유사 기사 1",
            "content": "AI 기술의 발전에 대한 내용입니다. " * 10,
            "publisher": "뉴스1",
            "published_at": datetime(2024, 1, 1, 13, 0, 0),
        },
    ]

    with patch("app.models.base.async_session_factory", mock_session_factory), \
         patch("app.core.analyzer.analyze_article") as mock_analyze, \
         patch("app.core.analyzer.find_similar_articles") as mock_find_similar, \
         patch("app.services.news_search.search_news") as mock_search_news, \
         patch("app.core.crawler.crawl_articles_batch") as mock_crawl, \
         patch("app.core.timeline.build_timeline") as mock_build_timeline, \
         patch("app.services.cache.cache_delete"):

        mock_analyze.side_effect = [
            (str(uuid.uuid4()), [0.1] * 768),  # Origin
            (str(uuid.uuid4()), [0.11] * 768),  # Article 1 only
        ]

        mock_search_news.return_value = mock_search_results
        mock_crawl.return_value = partial_crawled  # Only 1 article
        mock_find_similar.return_value = []
        mock_build_timeline.return_value = mock_timeline_entries

        # Run pipeline
        await _run_pipeline(mock_task, tracking_id, article_id)

        # Pipeline should complete successfully
        assert tracking_request.status == "completed"
        assert tracking_request.progress == 100

        # Only 2 embeddings created (origin + 1 crawled)
        assert mock_analyze.call_count == 2


@pytest.mark.anyio
async def test_pipeline_handles_no_search_results(
    tracking_id,
    article_id,
    tracking_request,
    origin_article,
    mock_session_factory,
    mock_db_session,
    mock_timeline_entries,
):
    """Test pipeline completes when Google News returns no results."""

    mock_task = MagicMock()

    with patch("app.models.base.async_session_factory", mock_session_factory), \
         patch("app.core.analyzer.analyze_article") as mock_analyze, \
         patch("app.core.analyzer.find_similar_articles") as mock_find_similar, \
         patch("app.services.news_search.search_news") as mock_search_news, \
         patch("app.core.crawler.crawl_articles_batch") as mock_crawl, \
         patch("app.core.timeline.build_timeline") as mock_build_timeline, \
         patch("app.services.cache.cache_delete"):

        mock_analyze.return_value = (str(uuid.uuid4()), [0.1] * 768)
        mock_search_news.return_value = []  # No search results
        mock_crawl.return_value = []  # No articles to crawl
        mock_find_similar.return_value = []

        # Timeline with just origin article
        origin_only_timeline = [
            {
                "article_id": article_id,
                "similarity_score": 1.0,
                "similarity_category": "origin",
                "lifecycle_stage": "origin",
                "is_origin": True,
            }
        ]
        mock_build_timeline.return_value = origin_only_timeline

        # Run pipeline
        await _run_pipeline(mock_task, tracking_id, article_id)

        # Pipeline should complete successfully
        assert tracking_request.status == "completed"
        assert tracking_request.progress == 100

        # Only origin article embedding created
        assert mock_analyze.call_count == 1

        # crawl_articles_batch should be called with empty list
        mock_crawl.assert_called_once_with([])


@pytest.mark.anyio
async def test_pipeline_marks_error_on_failure(
    tracking_id,
    article_id,
    tracking_request,
    origin_article,
    mock_session_factory,
    mock_db_session,
):
    """Test pipeline marks tracking as error when unexpected exception occurs."""

    mock_task = MagicMock()

    with patch("app.models.base.async_session_factory", mock_session_factory), \
         patch("app.core.analyzer.analyze_article") as mock_analyze, \
         patch("app.services.news_search.search_news") as mock_search_news:

        mock_analyze.return_value = (str(uuid.uuid4()), [0.1] * 768)

        # Simulate search_news raising an exception
        mock_search_news.side_effect = Exception("Network error")

        # Run pipeline - should catch exception
        with pytest.raises(Exception, match="Network error"):
            await _run_pipeline(mock_task, tracking_id, article_id)

        # Verify tracking was marked as error
        assert tracking_request.status == "error"
        assert tracking_request.error_message is not None
        assert "Network error" in tracking_request.error_message


@pytest.mark.anyio
async def test_pipeline_timeout_handling(
    tracking_id,
    article_id,
    tracking_request,
    origin_article,
    mock_session_factory,
    mock_db_session,
):
    """Test SoftTimeLimitExceeded is re-raised for outer handler."""

    mock_task = MagicMock()

    with patch("app.models.base.async_session_factory", mock_session_factory), \
         patch("app.core.analyzer.analyze_article") as mock_analyze:

        # Simulate timeout during analyze
        mock_analyze.side_effect = SoftTimeLimitExceeded()

        # Run pipeline - should re-raise SoftTimeLimitExceeded
        with pytest.raises(SoftTimeLimitExceeded):
            await _run_pipeline(mock_task, tracking_id, article_id)

        # Status should NOT be set to error (outer handler will handle it)
        assert tracking_request.status == "processing"


@pytest.mark.anyio
async def test_mark_failed_updates_tracking(
    tracking_id,
    tracking_request,
    mock_session_factory,
    mock_db_session,
):
    """Test _mark_failed correctly updates tracking status."""

    error_message = "분석 시간이 초과되었습니다. (10분 제한)"

    with patch("app.models.base.async_session_factory", mock_session_factory):
        await _mark_failed(tracking_id, error_message)

        # Verify tracking was updated
        assert tracking_request.status == "error"
        assert tracking_request.error_message == error_message

        # Verify commit was called
        mock_db_session.commit.assert_called_once()


@pytest.mark.anyio
async def test_mark_failed_handles_long_error_message(
    tracking_id,
    tracking_request,
    mock_session_factory,
    mock_db_session,
):
    """Test _mark_failed truncates error messages longer than 500 chars."""

    # Create error message longer than 500 chars
    long_error = "Error: " + "A" * 600

    with patch("app.models.base.async_session_factory", mock_session_factory):
        await _mark_failed(tracking_id, long_error)

        # Error message should be truncated to 500 chars
        assert len(tracking_request.error_message) <= 500
        assert tracking_request.error_message.startswith("Error: AAA")


@pytest.mark.anyio
async def test_mark_failed_handles_db_error(
    tracking_id,
    mock_session_factory,
):
    """Test _mark_failed handles database errors gracefully."""

    # Mock session that raises error on execute
    failing_session = AsyncMock()
    failing_session.execute = AsyncMock(side_effect=Exception("DB connection lost"))

    failing_factory = MagicMock()
    failing_factory.return_value.__aenter__ = AsyncMock(return_value=failing_session)
    failing_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.models.base.async_session_factory", failing_factory):
        # Should not raise exception - just log error
        await _mark_failed(tracking_id, "Some error")


@pytest.mark.anyio
async def test_pipeline_excludes_origin_from_crawl(
    tracking_id,
    article_id,
    tracking_request,
    origin_article,
    mock_session_factory,
    mock_db_session,
    mock_timeline_entries,
):
    """Test that origin article URL is excluded from crawl list."""

    mock_task = MagicMock()

    # Search results include the origin URL
    origin_url = "https://example.com/origin-article"
    search_with_origin = [
        {"title": "원본", "url": origin_url},  # Should be filtered out
        {"title": "유사1", "url": "https://example.com/article-1"},
        {"title": "유사2", "url": "https://example.com/article-2"},
    ]

    with patch("app.models.base.async_session_factory", mock_session_factory), \
         patch("app.core.analyzer.analyze_article") as mock_analyze, \
         patch("app.core.analyzer.find_similar_articles") as mock_find_similar, \
         patch("app.services.news_search.search_news") as mock_search_news, \
         patch("app.core.crawler.crawl_articles_batch") as mock_crawl, \
         patch("app.core.timeline.build_timeline") as mock_build_timeline, \
         patch("app.services.cache.cache_delete"):

        mock_analyze.return_value = (str(uuid.uuid4()), [0.1] * 768)
        mock_search_news.return_value = search_with_origin
        mock_crawl.return_value = []
        mock_find_similar.return_value = []
        mock_build_timeline.return_value = mock_timeline_entries

        await _run_pipeline(mock_task, tracking_id, article_id)

        # Verify origin URL was excluded from crawl
        crawl_urls = mock_crawl.call_args[0][0]
        assert origin_url not in crawl_urls
        assert len(crawl_urls) == 2  # Only 2 non-origin URLs
