"""Unit tests for category classification service."""
import pytest
from app.services.category import (
    normalize_category,
    classify_by_keywords,
    resolve_category,
    extract_category_from_html,
)


class TestNormalizeCategory:
    """Tests for normalize_category function."""

    def test_direct_korean_match(self):
        assert normalize_category("정치") == "politics"
        assert normalize_category("경제") == "economy"
        assert normalize_category("사회") == "society"
        assert normalize_category("스포츠") == "sports"

    def test_direct_english_match(self):
        assert normalize_category("politics") == "politics"
        assert normalize_category("economy") == "economy"
        assert normalize_category("tech") == "tech"

    def test_case_insensitive(self):
        assert normalize_category("Politics") == "politics"
        assert normalize_category("ECONOMY") == "economy"
        assert normalize_category("IT") == "tech"

    def test_partial_match(self):
        assert normalize_category("IT/과학") == "tech"
        assert normalize_category("사회/교육") == "society"

    def test_none_input(self):
        assert normalize_category(None) is None

    def test_empty_string(self):
        assert normalize_category("") is None

    def test_unknown_category(self):
        assert normalize_category("xyz_unknown") is None


class TestClassifyByKeywords:
    """Tests for classify_by_keywords function."""

    def test_politics_keywords(self):
        assert classify_by_keywords("대통령 국회 발언") == "politics"

    def test_economy_keywords(self):
        assert classify_by_keywords("코스피 주가 상승") == "economy"

    def test_tech_keywords(self):
        assert classify_by_keywords("AI 인공지능 신기술") == "tech"

    def test_sports_keywords(self):
        assert classify_by_keywords("손흥민 프리미어리그 골") == "sports"

    def test_entertainment_keywords(self):
        assert classify_by_keywords("BTS 콘서트 앨범") == "entertainment"

    def test_no_match(self):
        assert classify_by_keywords("아무 관련 없는 문장") is None

    def test_empty_title(self):
        assert classify_by_keywords("") is None

    def test_highest_score_wins(self):
        # More economy keywords than tech
        result = classify_by_keywords("삼성 코스피 주가 금리 환율")
        assert result == "economy"


class TestResolveCategory:
    """Tests for resolve_category function (3-tier fallback)."""

    def test_source_category_priority(self):
        """source_category takes highest priority."""
        result = resolve_category(
            source_category="politics",
            feed_category="economy",
            title="AI 기술 발전",
        )
        assert result == "politics"

    def test_feed_category_fallback(self):
        """feed_category used when no source_category."""
        result = resolve_category(
            source_category=None,
            feed_category="economy",
            title="일반 뉴스",
        )
        assert result == "economy"

    def test_keyword_fallback(self):
        """Keywords used when no source/feed category."""
        result = resolve_category(
            source_category=None,
            feed_category=None,
            title="대통령 국회 발언 논란",
        )
        assert result == "politics"

    def test_headlines_feed_deprioritized(self):
        """headlines feed_category is skipped in favor of keywords."""
        result = resolve_category(
            source_category=None,
            feed_category="headlines",
            title="AI 인공지능 반도체",
        )
        assert result == "tech"

    def test_headlines_final_fallback(self):
        """headlines used as final fallback when keywords don't match."""
        result = resolve_category(
            source_category=None,
            feed_category="headlines",
            title="일반적인 뉴스 제목",
        )
        assert result == "headlines"

    def test_all_none(self):
        """Returns None when nothing matches."""
        result = resolve_category(
            source_category=None,
            feed_category=None,
            title=None,
        )
        assert result is None

    def test_invalid_source_category(self):
        """Non-standard source_category falls through."""
        result = resolve_category(
            source_category="invalid_cat",
            feed_category="tech",
            title="테스트",
        )
        assert result == "tech"


class TestExtractCategoryFromHtml:
    """Tests for extract_category_from_html function."""

    def test_article_section_meta(self):
        html = '<meta property="article:section" content="경제">'
        assert extract_category_from_html(html) == "economy"

    def test_og_article_section(self):
        html = '<meta property="og:article:section" content="정치">'
        assert extract_category_from_html(html) == "politics"

    def test_news_keywords_fallback(self):
        html = '<meta name="news_keywords" content="스포츠, 야구, KBO">'
        assert extract_category_from_html(html) == "sports"

    def test_no_meta_tags(self):
        html = '<html><body>No meta tags here</body></html>'
        assert extract_category_from_html(html) is None

    def test_unrecognized_category(self):
        html = '<meta property="article:section" content="randomxyz">'
        assert extract_category_from_html(html) is None
