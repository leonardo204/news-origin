"""Unit tests for embedding service (Azure OpenAI API based)."""
import pytest
from unittest.mock import patch


class TestCreateEmbedding:
    """Tests for create_embedding function."""

    @patch('app.services.embedding.create_embedding_sync')
    def test_create_embedding_basic(self, mock_sync):
        """Test creating embedding for a simple text."""
        from app.services.embedding import create_embedding

        mock_sync.return_value = [0.1, 0.2, 0.3]
        result = create_embedding("test text")

        mock_sync.assert_called_once_with("test text")
        assert result == [0.1, 0.2, 0.3]

    @patch('app.services.embedding.create_embedding_sync')
    def test_create_embedding_empty_string(self, mock_sync):
        """Test creating embedding for empty string."""
        from app.services.embedding import create_embedding

        mock_sync.return_value = [0.0, 0.0, 0.0]
        result = create_embedding("")

        mock_sync.assert_called_once_with("")
        assert result == [0.0, 0.0, 0.0]


class TestCreateEmbeddingsBatch:
    """Tests for create_embeddings_batch function."""

    @patch('app.services.embedding.create_embeddings_batch_sync')
    def test_batch_basic(self, mock_batch_sync):
        """Test creating embeddings for multiple texts."""
        from app.services.embedding import create_embeddings_batch

        mock_batch_sync.return_value = [[0.1, 0.2], [0.3, 0.4]]
        result = create_embeddings_batch(["text 1", "text 2"])

        mock_batch_sync.assert_called_once_with(["text 1", "text 2"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @patch('app.services.embedding.create_embeddings_batch_sync')
    def test_batch_empty_list(self, mock_batch_sync):
        """Test creating embeddings for empty list."""
        from app.services.embedding import create_embeddings_batch

        mock_batch_sync.return_value = []
        result = create_embeddings_batch([])

        mock_batch_sync.assert_called_once_with([])
        assert result == []


class TestGetArticleText:
    """Tests for get_article_text function."""

    def test_title_only(self):
        """Test returns title as-is."""
        from app.services.embedding import get_article_text

        result = get_article_text("Test Title")
        assert result == "Test Title"

    def test_korean_title(self):
        """Test with Korean title."""
        from app.services.embedding import get_article_text

        result = get_article_text("한국 뉴스 제목 테스트")
        assert result == "한국 뉴스 제목 테스트"

    def test_special_chars(self):
        """Test with special characters in title."""
        from app.services.embedding import get_article_text

        result = get_article_text("Test: Title & More! <html>")
        assert result == "Test: Title & More! <html>"

    def test_empty_title(self):
        """Test with empty string title."""
        from app.services.embedding import get_article_text

        result = get_article_text("")
        assert result == ""
