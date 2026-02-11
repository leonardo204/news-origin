"""Unit tests for news_search service."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import httpx
import xml.etree.ElementTree as ET


class TestSearchNews:
    """Tests for search_news function."""

    @pytest.mark.anyio
    @patch('app.services.news_search._search_google_news_rss')
    @patch('app.services.news_search.settings')
    async def test_search_news_with_google_rss(self, mock_settings, mock_google_rss):
        """Test search using Google News RSS."""
        from app.services.news_search import search_news

        mock_settings.gnews_api_key = None

        expected_results = [
            {"title": "Article 1", "url": "https://example.com/1", "publisher": "News1", "published_at": datetime(2024, 1, 1)},
            {"title": "Article 2", "url": "https://example.com/2", "publisher": "News2", "published_at": datetime(2024, 1, 2)}
        ]
        mock_google_rss.return_value = expected_results

        results = await search_news("climate change", limit=10)

        mock_google_rss.assert_called_once_with("climate change", 10)
        assert results == expected_results

    @pytest.mark.anyio
    @patch('app.services.news_search._search_google_news_rss')
    @patch('app.services.news_search._search_gnews')
    @patch('app.services.news_search.settings')
    async def test_search_news_fallback_to_gnews(self, mock_settings, mock_gnews, mock_google_rss):
        """Test fallback to GNews when RSS returns fewer results."""
        from app.services.news_search import search_news

        mock_settings.gnews_api_key = "test-key"

        mock_google_rss.return_value = [{"title": "Article 1", "url": "https://example.com/1"}]  # Only 1 result
        mock_gnews.return_value = [{"title": "GNews Article", "url": "https://gnews.io/1"}]

        results = await search_news("technology", limit=5)

        mock_google_rss.assert_called_once()
        mock_gnews.assert_called_once_with("technology", 4)  # limit - len(google_results)
        assert len(results) == 2

    @pytest.mark.anyio
    @patch('app.services.news_search._search_google_news_rss')
    @patch('app.services.news_search.settings')
    async def test_search_news_both_fail(self, mock_settings, mock_google_rss):
        """Test when both sources fail."""
        from app.services.news_search import search_news

        mock_settings.gnews_api_key = None
        mock_google_rss.return_value = []

        results = await search_news("query", limit=10)

        assert results == []


class TestSearchGoogleNewsRss:
    """Tests for _search_google_news_rss function."""

    @pytest.mark.anyio
    @patch('app.services.news_search.httpx.AsyncClient')
    @patch('app.services.news_search._parse_rfc2822')
    @patch('app.services.news_search._clean_title')
    async def test_search_google_news_rss_success(
        self, mock_clean_title, mock_parse_rfc, mock_client_class
    ):
        """Test successful Google News RSS parsing."""
        from app.services.news_search import _search_google_news_rss

        # Create XML response
        rss_xml = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Article 1 - Source 1</title>
                    <link>https://example.com/1</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                    <source>Source 1</source>
                </item>
                <item>
                    <title>Article 2 - Source 2</title>
                    <link>https://example.com/2</link>
                    <pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate>
                    <source>Source 2</source>
                </item>
            </channel>
        </rss>
        """

        mock_response = Mock()
        mock_response.text = rss_xml
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Mock helpers
        mock_parse_rfc.side_effect = [
            datetime(2024, 1, 1, 12, 0, 0),
            datetime(2024, 1, 2, 12, 0, 0)
        ]
        mock_clean_title.side_effect = ["Article 1", "Article 2"]

        results = await _search_google_news_rss("test query", limit=10)

        assert len(results) == 2
        assert results[0]["title"] == "Article 1"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["publisher"] == "Source 1"
        assert results[0]["published_at"] == datetime(2024, 1, 1, 12, 0, 0)

    @pytest.mark.anyio
    @patch('app.services.news_search.httpx.AsyncClient')
    async def test_search_google_news_rss_http_error(self, mock_client_class):
        """Test HTTP error handling."""
        from app.services.news_search import _search_google_news_rss

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        mock_client_class.return_value = mock_client

        results = await _search_google_news_rss("query")

        assert results == []

    @pytest.mark.anyio
    @patch('app.services.news_search.httpx.AsyncClient')
    async def test_search_google_news_rss_parse_error(self, mock_client_class):
        """Test XML parse error handling."""
        from app.services.news_search import _search_google_news_rss

        mock_response = Mock()
        mock_response.text = "invalid xml"
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        results = await _search_google_news_rss("query")

        assert results == []


class TestSearchGnews:
    """Tests for _search_gnews function."""

    @pytest.mark.anyio
    @patch('app.services.news_search.httpx.AsyncClient')
    @patch('app.services.news_search._parse_iso')
    @patch('app.services.news_search.settings')
    async def test_search_gnews_success(self, mock_settings, mock_parse_iso, mock_client_class):
        """Test successful GNews API search."""
        from app.services.news_search import _search_gnews

        mock_settings.gnews_api_key = "test_api_key"

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "articles": [
                {
                    "title": "GNews Article 1",
                    "url": "https://gnews.io/1",
                    "publishedAt": "2024-01-01T12:00:00Z",
                    "source": {"name": "GNews Source"}
                },
                {
                    "title": "GNews Article 2",
                    "url": "https://gnews.io/2",
                    "publishedAt": "2024-01-02T12:00:00Z",
                    "source": {"name": "Another Source"}
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        mock_parse_iso.side_effect = [
            datetime(2024, 1, 1, 12, 0, 0),
            datetime(2024, 1, 2, 12, 0, 0)
        ]

        results = await _search_gnews("test query", limit=10)

        assert len(results) == 2
        assert results[0]["title"] == "GNews Article 1"
        assert results[0]["url"] == "https://gnews.io/1"
        assert results[0]["publisher"] == "GNews Source"
        assert results[0]["published_at"] == datetime(2024, 1, 1, 12, 0, 0)

    @pytest.mark.anyio
    @patch('app.services.news_search.settings')
    async def test_search_gnews_no_api_key(self, mock_settings):
        """Test when API key is not configured."""
        from app.services.news_search import _search_gnews

        mock_settings.gnews_api_key = None

        results = await _search_gnews("query")

        assert results == []

    @pytest.mark.anyio
    @patch('app.services.news_search.httpx.AsyncClient')
    @patch('app.services.news_search.settings')
    async def test_search_gnews_http_error(self, mock_settings, mock_client_class):
        """Test HTTP error handling."""
        from app.services.news_search import _search_gnews

        mock_settings.gnews_api_key = "test_key"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("API error"))
        mock_client_class.return_value = mock_client

        results = await _search_gnews("query")

        assert results == []


class TestParseRfc2822:
    """Tests for _parse_rfc2822 function."""

    def test_parse_rfc2822_valid(self):
        """Test parsing valid RFC2822 date."""
        from app.services.news_search import _parse_rfc2822

        result = _parse_rfc2822("Mon, 01 Jan 2024 12:30:00 GMT")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 30

    def test_parse_rfc2822_with_timezone(self):
        """Test parsing RFC2822 with timezone."""
        from app.services.news_search import _parse_rfc2822

        result = _parse_rfc2822("Tue, 15 Feb 2024 08:00:00 +0000")
        assert result is not None
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 15

    def test_parse_rfc2822_invalid(self):
        """Test parsing invalid RFC2822 date."""
        from app.services.news_search import _parse_rfc2822

        result = _parse_rfc2822("invalid date string")
        assert result is None

    def test_parse_rfc2822_none(self):
        """Test parsing None."""
        from app.services.news_search import _parse_rfc2822

        result = _parse_rfc2822(None)
        assert result is None

    def test_parse_rfc2822_empty_string(self):
        """Test parsing empty string."""
        from app.services.news_search import _parse_rfc2822

        result = _parse_rfc2822("")
        assert result is None


class TestParseIso:
    """Tests for _parse_iso function."""

    def test_parse_iso_with_z(self):
        """Test parsing ISO with Z suffix (converted to +00:00)."""
        from app.services.news_search import _parse_iso

        result = _parse_iso("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_iso_with_timezone(self):
        """Test parsing ISO with timezone."""
        from app.services.news_search import _parse_iso

        result = _parse_iso("2024-03-20T15:45:30+05:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 20

    def test_parse_iso_invalid(self):
        """Test parsing invalid ISO date."""
        from app.services.news_search import _parse_iso

        result = _parse_iso("not a date")
        assert result is None

    def test_parse_iso_none(self):
        """Test parsing None."""
        from app.services.news_search import _parse_iso

        result = _parse_iso(None)
        assert result is None

    def test_parse_iso_empty_string(self):
        """Test parsing empty string."""
        from app.services.news_search import _parse_iso

        result = _parse_iso("")
        assert result is None


class TestCleanTitle:
    """Tests for _clean_title function."""

    def test_clean_title_with_source_suffix(self):
        """Test removing source suffix from title."""
        from app.services.news_search import _clean_title

        result = _clean_title("Breaking News - BBC News", "BBC News")
        assert result == "Breaking News"

    def test_clean_title_with_dash_separator(self):
        """Test title with dash separator."""
        from app.services.news_search import _clean_title

        result = _clean_title("Article Title - CNN", "CNN")
        assert result == "Article Title"

    def test_clean_title_no_source_in_title(self):
        """Test title without source suffix."""
        from app.services.news_search import _clean_title

        result = _clean_title("Just a Title", "Source")
        assert result == "Just a Title"

    def test_clean_title_source_in_middle(self):
        """Test when source appears in middle of title."""
        from app.services.news_search import _clean_title

        result = _clean_title("BBC News reports on weather - BBC News", "BBC News")
        # Should only remove the suffix
        assert result == "BBC News reports on weather"

    def test_clean_title_multiple_dashes(self):
        """Test title with multiple dashes."""
        from app.services.news_search import _clean_title

        result = _clean_title("Part 1 - Part 2 - Source", "Source")
        assert result == "Part 1 - Part 2"

    def test_clean_title_none_source(self):
        """Test with None source."""
        from app.services.news_search import _clean_title

        result = _clean_title("Title - Source", None)
        # Should return title as-is when source is None
        assert result == "Title - Source"

    def test_clean_title_case_sensitive(self):
        """Test that cleaning is case-sensitive."""
        from app.services.news_search import _clean_title

        result = _clean_title("Article - bbc news", "BBC News")
        # Should not match different case
        assert result == "Article - bbc news"
