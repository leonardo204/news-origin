"""
Test module for app.core.analyzer

Tests:
- classify_similarity with boundary values
- analyze_article with mocked dependencies
- find_similar_articles with various scenarios
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.core.analyzer import classify_similarity, analyze_article, find_similar_articles


class TestClassifySimilarity:
    """Test similarity score classification"""

    @patch("app.core.analyzer.settings")
    def test_same_category_at_threshold(self, mock_settings):
        """Score exactly at same threshold returns 'same'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.90) == "same"

    @patch("app.core.analyzer.settings")
    def test_same_category_above_threshold(self, mock_settings):
        """Score above same threshold returns 'same'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(1.0) == "same"
        assert classify_similarity(0.95) == "same"

    @patch("app.core.analyzer.settings")
    def test_derivative_category_at_threshold(self, mock_settings):
        """Score exactly at derivative threshold returns 'derivative'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.75) == "derivative"

    @patch("app.core.analyzer.settings")
    def test_derivative_category_just_below_same(self, mock_settings):
        """Score just below same threshold returns 'derivative'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.89) == "derivative"

    @patch("app.core.analyzer.settings")
    def test_related_category_at_threshold(self, mock_settings):
        """Score exactly at related threshold returns 'related'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.60) == "related"

    @patch("app.core.analyzer.settings")
    def test_related_category_just_below_derivative(self, mock_settings):
        """Score just below derivative threshold returns 'related'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.74) == "related"

    @patch("app.core.analyzer.settings")
    def test_isolated_category_just_below_related(self, mock_settings):
        """Score just below related threshold returns 'isolated'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.59) == "isolated"

    @patch("app.core.analyzer.settings")
    def test_isolated_category_zero_score(self, mock_settings):
        """Zero score returns 'isolated'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(0.0) == "isolated"

    @patch("app.core.analyzer.settings")
    def test_isolated_category_negative_score(self, mock_settings):
        """Negative score returns 'isolated'"""
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        assert classify_similarity(-0.1) == "isolated"


class TestAnalyzeArticle:
    """Test article analysis with embedding creation and storage"""

    @patch("app.core.analyzer.upsert_embedding")
    @patch("app.core.analyzer.create_embedding")
    @patch("app.core.analyzer.get_article_text")
    def test_analyze_article_with_full_data(
        self, mock_get_text, mock_create_embedding, mock_upsert
    ):
        """Analyze article with all fields provided"""
        # Arrange
        mock_get_text.return_value = "완전한 기사 제목과 본문"
        mock_create_embedding.return_value = [0.1] * 768
        mock_upsert.return_value = "point_12345"

        # Act
        point_id, embedding = analyze_article(
            article_id="article_001",
            title="한국 경제 뉴스 제목",
            content="상세한 경제 뉴스 본문입니다.",
            publisher="한국경제신문",
            published_at="2024-01-15T10:00:00Z",
        )

        # Assert
        mock_get_text.assert_called_once_with("한국 경제 뉴스 제목", "상세한 경제 뉴스 본문입니다.")
        mock_create_embedding.assert_called_once_with("완전한 기사 제목과 본문")
        mock_upsert.assert_called_once_with(
            "article_001",
            [0.1] * 768,
            {
                "title": "한국 경제 뉴스 제목",
                "publisher": "한국경제신문",
                "published_at": "2024-01-15T10:00:00Z",
            },
        )
        assert point_id == "point_12345"
        assert embedding == [0.1] * 768

    @patch("app.core.analyzer.upsert_embedding")
    @patch("app.core.analyzer.create_embedding")
    @patch("app.core.analyzer.get_article_text")
    def test_analyze_article_title_only(
        self, mock_get_text, mock_create_embedding, mock_upsert
    ):
        """Analyze article with title only"""
        # Arrange
        mock_get_text.return_value = "제목만 있는 기사"
        mock_create_embedding.return_value = [0.2] * 768
        mock_upsert.return_value = "point_67890"

        # Act
        point_id, embedding = analyze_article(
            article_id="article_002",
            title="제목만 있는 기사",
        )

        # Assert
        mock_get_text.assert_called_once_with("제목만 있는 기사", None)
        mock_create_embedding.assert_called_once_with("제목만 있는 기사")
        mock_upsert.assert_called_once_with(
            "article_002",
            [0.2] * 768,
            {
                "title": "제목만 있는 기사",
                "publisher": None,
                "published_at": None,
            },
        )
        assert point_id == "point_67890"
        assert embedding == [0.2] * 768

    @patch("app.core.analyzer.upsert_embedding")
    @patch("app.core.analyzer.create_embedding")
    @patch("app.core.analyzer.get_article_text")
    def test_analyze_article_korean_characters(
        self, mock_get_text, mock_create_embedding, mock_upsert
    ):
        """Analyze article with various Korean characters"""
        # Arrange
        mock_get_text.return_value = "특수문자 포함: 한글, 숫자123, 기호!@#"
        mock_create_embedding.return_value = [0.3] * 768
        mock_upsert.return_value = "point_korean"

        # Act
        point_id, embedding = analyze_article(
            article_id="article_korean",
            title="특수문자 포함: 한글, 숫자123, 기호!@#",
            content="본문에도 다양한 문자가 포함됩니다: ①②③ ㄱㄴㄷ",
            publisher="테스트 신문사",
        )

        # Assert
        mock_get_text.assert_called_once()
        mock_create_embedding.assert_called_once()
        assert point_id == "point_korean"


class TestFindSimilarArticles:
    """Test finding similar articles with vector search"""

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_basic(self, mock_search, mock_settings):
        """Find similar articles without exclusion"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        mock_search.return_value = [
            {"id": "art_1", "score": 0.95, "payload": {"article_id": "art_1", "title": "매우 유사한 기사"}},
            {"id": "art_2", "score": 0.80, "payload": {"article_id": "art_2", "title": "파생 기사"}},
            {"id": "art_3", "score": 0.65, "payload": {"article_id": "art_3", "title": "관련 기사"}},
        ]

        # Act
        results = find_similar_articles([0.1] * 768, limit=50)

        # Assert
        mock_search.assert_called_once_with(
            embedding=[0.1] * 768,
            limit=51,
            score_threshold=0.60,
        )
        assert len(results) == 3
        assert results[0]["category"] == "same"
        assert results[1]["category"] == "derivative"
        assert results[2]["category"] == "related"

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_with_exclusion(self, mock_search, mock_settings):
        """Find similar articles excluding specific article"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        mock_search.return_value = [
            {"id": "art_1", "score": 1.0, "payload": {"article_id": "art_self", "title": "자기 자신"}},
            {"id": "art_2", "score": 0.95, "payload": {"article_id": "art_2", "title": "다른 기사"}},
            {"id": "art_3", "score": 0.80, "payload": {"article_id": "art_3", "title": "또 다른 기사"}},
        ]

        # Act
        results = find_similar_articles(
            [0.1] * 768,
            exclude_article_id="art_self",
            limit=50,
        )

        # Assert
        assert len(results) == 2
        assert all(r["payload"]["article_id"] != "art_self" for r in results)
        assert results[0]["payload"]["article_id"] == "art_2"
        assert results[1]["payload"]["article_id"] == "art_3"

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_respects_limit(self, mock_search, mock_settings):
        """Find similar articles respects limit parameter"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        # Return more results than limit
        mock_search.return_value = [
            {"id": f"art_{i}", "score": 0.9 - i * 0.01, "payload": {"article_id": f"art_{i}"}}
            for i in range(100)
        ]

        # Act
        results = find_similar_articles([0.1] * 768, limit=10)

        # Assert
        assert len(results) == 10
        mock_search.assert_called_once_with(
            embedding=[0.1] * 768,
            limit=11,
            score_threshold=0.60,
        )

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_empty_results(self, mock_search, mock_settings):
        """Find similar articles with no results"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        mock_search.return_value = []

        # Act
        results = find_similar_articles([0.1] * 768)

        # Assert
        assert len(results) == 0

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_all_isolated(self, mock_search, mock_settings):
        """Find similar articles where all are isolated category"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        mock_search.return_value = [
            {"id": "art_1", "score": 0.59, "payload": {"article_id": "art_1"}},
            {"id": "art_2", "score": 0.50, "payload": {"article_id": "art_2"}},
        ]

        # Act
        results = find_similar_articles([0.1] * 768)

        # Assert
        assert len(results) == 2
        assert all(r["category"] == "isolated" for r in results)

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_mixed_categories(self, mock_search, mock_settings):
        """Find similar articles with mixed similarity categories"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        mock_search.return_value = [
            {"id": "art_1", "score": 0.95, "payload": {"article_id": "art_1", "title": "동일 기사"}},
            {"id": "art_2", "score": 0.85, "payload": {"article_id": "art_2", "title": "파생 기사"}},
            {"id": "art_3", "score": 0.70, "payload": {"article_id": "art_3", "title": "관련 기사"}},
            {"id": "art_4", "score": 0.55, "payload": {"article_id": "art_4", "title": "독립 기사"}},
        ]

        # Act
        results = find_similar_articles([0.1] * 768)

        # Assert
        assert len(results) == 4
        assert results[0]["category"] == "same"
        assert results[1]["category"] == "derivative"
        assert results[2]["category"] == "related"
        assert results[3]["category"] == "isolated"

    @patch("app.core.analyzer.settings")
    @patch("app.core.analyzer.search_similar")
    def test_find_similar_exclusion_with_limit(self, mock_search, mock_settings):
        """Find similar articles with exclusion and limit together"""
        # Arrange
        mock_settings.similarity_same_threshold = 0.90
        mock_settings.similarity_derivative_threshold = 0.75
        mock_settings.similarity_related_threshold = 0.60

        mock_search.return_value = [
            {"id": "art_self", "score": 1.0, "payload": {"article_id": "art_self"}},
            {"id": "art_1", "score": 0.95, "payload": {"article_id": "art_1"}},
            {"id": "art_2", "score": 0.90, "payload": {"article_id": "art_2"}},
            {"id": "art_3", "score": 0.85, "payload": {"article_id": "art_3"}},
        ]

        # Act - limit=2 but should get 2 after excluding self
        results = find_similar_articles(
            [0.1] * 768,
            exclude_article_id="art_self",
            limit=2,
        )

        # Assert
        assert len(results) == 2
        assert results[0]["payload"]["article_id"] == "art_1"
        assert results[1]["payload"]["article_id"] == "art_2"
