"""Unit tests for crawler service."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import httpx


class TestCrawlArticle:
    """Tests for crawl_article function."""

    @pytest.mark.anyio
    @patch('app.core.crawler._fetch_html')
    @patch('app.core.crawler._extract_with_trafilatura')
    async def test_crawl_article_success_with_trafilatura(self, mock_extract_traf, mock_fetch):
        """Test successful article crawl with trafilatura."""
        from app.core.crawler import crawl_article

        url = "https://example.com/article"
        html = "<html><body>Article content</body></html>"
        expected_article = {
            "title": "Test Article",
            "content": "Article content here",
            "author": "John Doe",
            "publisher": "Test Site",
            "published_at": datetime(2024, 1, 1),
            "summary": "Article content here...",
            "language": "ko"
        }

        mock_fetch.return_value = html
        mock_extract_traf.return_value = expected_article

        result = await crawl_article(url)

        mock_fetch.assert_called_once_with(url)
        mock_extract_traf.assert_called_once_with(html, url)
        assert result["title"] == "Test Article"
        assert result["url"] == url
        assert result["publisher_domain"] == "example.com"

    @pytest.mark.anyio
    @patch('app.core.crawler._fetch_html')
    @patch('app.core.crawler._extract_with_trafilatura')
    @patch('app.core.crawler._extract_with_newspaper')
    async def test_crawl_article_fallback_to_newspaper(self, mock_extract_news, mock_extract_traf, mock_fetch):
        """Test fallback to newspaper4k when trafilatura fails."""
        from app.core.crawler import crawl_article

        url = "https://example.com/article"
        html = "<html><body>Content</body></html>"
        expected_article = {
            "title": "News Article",
            "content": "News content",
            "author": "Jane Smith",
            "publisher": "example.com",
            "published_at": datetime(2024, 2, 1),
            "summary": "News content..."
        }

        mock_fetch.return_value = html
        mock_extract_traf.return_value = None  # Trafilatura fails
        mock_extract_news.return_value = expected_article

        result = await crawl_article(url)

        mock_extract_traf.assert_called_once()
        mock_extract_news.assert_called_once_with(url)
        assert result["title"] == "News Article"
        assert result["url"] == url
        assert result["publisher_domain"] == "example.com"

    @pytest.mark.anyio
    @patch('app.core.crawler._fetch_html')
    async def test_crawl_article_no_html(self, mock_fetch):
        """Test when HTML fetch fails."""
        from app.core.crawler import crawl_article

        mock_fetch.return_value = None

        result = await crawl_article("https://example.com/article")

        assert result is None

    @pytest.mark.anyio
    @patch('app.core.crawler._fetch_html')
    @patch('app.core.crawler._extract_with_trafilatura')
    @patch('app.core.crawler._extract_with_newspaper')
    async def test_crawl_article_both_extractors_fail(self, mock_extract_news, mock_extract_traf, mock_fetch):
        """Test when both extractors fail."""
        from app.core.crawler import crawl_article

        mock_fetch.return_value = "<html></html>"
        mock_extract_traf.return_value = None
        mock_extract_news.return_value = None

        result = await crawl_article("https://example.com/article")

        assert result is None


class TestCrawlArticlesBatch:
    """Tests for crawl_articles_batch function."""

    @pytest.mark.anyio
    @patch('app.core.crawler.crawl_article')
    @patch('app.core.crawler.asyncio.sleep')
    async def test_crawl_articles_batch_success(self, mock_sleep, mock_crawl):
        """Test batch crawling multiple articles."""
        from app.core.crawler import crawl_articles_batch

        urls = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://example.com/article3"
        ]

        articles = [
            {"title": "Article 1", "url": urls[0]},
            {"title": "Article 2", "url": urls[1]},
            {"title": "Article 3", "url": urls[2]}
        ]

        # Mock crawl_article to return different articles
        mock_crawl.side_effect = articles

        results = await crawl_articles_batch(urls)

        assert len(results) == 3
        assert mock_crawl.call_count == 3
        assert results == articles

    @pytest.mark.anyio
    @patch('app.core.crawler.crawl_article')
    @patch('app.core.crawler.asyncio.sleep')
    async def test_crawl_articles_batch_partial_success(self, mock_sleep, mock_crawl):
        """Test batch crawling with some failures."""
        from app.core.crawler import crawl_articles_batch

        urls = ["https://example.com/1", "https://example.com/2"]

        # First succeeds, second fails
        mock_crawl.side_effect = [
            {"title": "Article 1"},
            None
        ]

        results = await crawl_articles_batch(urls)

        assert len(results) == 1
        assert results[0]["title"] == "Article 1"

    @pytest.mark.anyio
    @patch('app.core.crawler.crawl_article')
    async def test_crawl_articles_batch_empty_list(self, mock_crawl):
        """Test batch crawling with empty URL list."""
        from app.core.crawler import crawl_articles_batch

        results = await crawl_articles_batch([])

        assert results == []
        mock_crawl.assert_not_called()


class TestFetchHtml:
    """Tests for _fetch_html function."""

    @pytest.mark.anyio
    @patch('app.core.crawler.httpx.AsyncClient')
    async def test_fetch_html_success(self, mock_client_class):
        """Test successful HTML fetch."""
        from app.core.crawler import _fetch_html

        mock_response = Mock()
        mock_response.text = "<html><body>Content</body></html>"
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        html = await _fetch_html("https://example.com")

        assert html == "<html><body>Content</body></html>"
        mock_client.get.assert_called_once()

    @pytest.mark.anyio
    @patch('app.core.crawler.httpx.AsyncClient')
    async def test_fetch_html_http_error(self, mock_client_class):
        """Test HTML fetch with HTTP error."""
        from app.core.crawler import _fetch_html

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        mock_client_class.return_value = mock_client

        html = await _fetch_html("https://example.com")

        assert html is None


class TestExtractWithTrafilatura:
    """Tests for _extract_with_trafilatura function."""

    @patch('app.core.crawler._parse_date')
    def test_extract_with_trafilatura_success(self, mock_parse_date):
        """Test successful extraction with trafilatura."""
        from app.core.crawler import _extract_with_trafilatura
        import json

        html = "<html><body>Article</body></html>"
        url = "https://example.com/article"

        # trafilatura.extract returns JSON string
        traf_data = {
            "title": "Test Article",
            "text": "Extracted content here",
            "author": "John Doe",
            "sitename": "Example News",
            "date": "2024-01-01",
            "language": "en"
        }

        mock_parse_date.return_value = datetime(2024, 1, 1)

        with patch('trafilatura.extract') as mock_extract:
            mock_extract.return_value = json.dumps(traf_data)

            result = _extract_with_trafilatura(html, url)

        assert result is not None
        assert result["title"] == "Test Article"
        assert result["content"] == "Extracted content here"
        assert result["author"] == "John Doe"
        assert result["publisher"] == "Example News"
        assert result["published_at"] == datetime(2024, 1, 1)
        assert result["summary"] == "Extracted content here..."
        assert result["language"] == "en"

    def test_extract_with_trafilatura_no_content(self):
        """Test when trafilatura extracts no content."""
        from app.core.crawler import _extract_with_trafilatura

        with patch('trafilatura.extract') as mock_extract:
            mock_extract.return_value = None

            result = _extract_with_trafilatura("<html></html>", "https://example.com")

        assert result is None

    def test_extract_with_trafilatura_exception(self):
        """Test exception handling in trafilatura extraction."""
        from app.core.crawler import _extract_with_trafilatura

        with patch('trafilatura.extract') as mock_extract:
            mock_extract.side_effect = Exception("Extraction error")

            result = _extract_with_trafilatura("<html></html>", "https://example.com")

        assert result is None


class TestExtractWithNewspaper:
    """Tests for _extract_with_newspaper function."""

    @pytest.mark.anyio
    async def test_extract_with_newspaper_success(self):
        """Test successful extraction with newspaper4k."""
        from app.core.crawler import _extract_with_newspaper

        url = "https://example.com/article"

        with patch('newspaper.Article') as mock_article_class:
            mock_article = Mock()
            mock_article.download = Mock()
            mock_article.parse = Mock()
            mock_article.title = "News Title"
            mock_article.text = "News content here"
            mock_article.authors = ["Jane Smith"]
            mock_article.publish_date = datetime(2024, 2, 1)
            mock_article_class.return_value = mock_article

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_executor = AsyncMock()
                mock_executor.side_effect = [None, None]  # download, parse
                mock_loop.return_value.run_in_executor = mock_executor

                result = await _extract_with_newspaper(url)

        assert result is not None
        assert result["title"] == "News Title"
        assert result["content"] == "News content here"
        assert result["author"] == "Jane Smith"
        assert result["publisher"] == "example.com"
        assert result["published_at"] == datetime(2024, 2, 1)

    @pytest.mark.anyio
    async def test_extract_with_newspaper_exception(self):
        """Test exception handling in newspaper extraction."""
        from app.core.crawler import _extract_with_newspaper

        with patch('newspaper.Article') as mock_article_class:
            mock_article_class.side_effect = Exception("Download error")

            result = await _extract_with_newspaper("https://example.com")

        assert result is None


class TestParseDate:
    """Tests for _parse_date function."""

    def test_parse_date_iso_format_without_z(self):
        """Test parsing ISO format date without Z suffix."""
        from app.core.crawler import _parse_date

        # Python 3.9 fromisoformat doesn't support Z, so use +00:00
        result = _parse_date("2024-01-15T10:30:00+00:00")
        # Result has timezone info, so compare without it or compare year/month/day
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_date_iso_with_z_fails_in_py39(self):
        """Test that Z suffix fails in Python 3.9 and falls back to strptime."""
        from app.core.crawler import _parse_date

        # "Z" suffix will fail fromisoformat in Python 3.9
        # It will try strptime with "%Y-%m-%d" which also fails
        result = _parse_date("2024-01-15T10:30:00Z")
        # In Python 3.9, this returns None because both parsers fail
        assert result is None

    def test_parse_date_simple_format(self):
        """Test parsing YYYY-MM-DD format."""
        from app.core.crawler import _parse_date

        result = _parse_date("2024-03-20")
        assert result == datetime(2024, 3, 20)

    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format."""
        from app.core.crawler import _parse_date

        result = _parse_date("invalid-date")
        assert result is None

    def test_parse_date_none(self):
        """Test parsing None."""
        from app.core.crawler import _parse_date

        result = _parse_date(None)
        assert result is None

    def test_parse_date_empty_string(self):
        """Test parsing empty string."""
        from app.core.crawler import _parse_date

        result = _parse_date("")
        assert result is None

    def test_parse_date_partial_iso(self):
        """Test parsing partial ISO format."""
        from app.core.crawler import _parse_date

        result = _parse_date("2024-01-01T00:00:00")
        assert result == datetime(2024, 1, 1, 0, 0, 0)
