"""Unit tests for embedding service."""
import pytest
from unittest.mock import Mock, patch
import numpy as np


@pytest.fixture(autouse=True)
def reset_global_model():
    """Reset the global _model variable before each test."""
    from app.services import embedding
    embedding._model = None
    yield
    embedding._model = None


class TestGetModel:
    """Tests for get_model function."""

    def test_get_model_creates_instance(self):
        """Test that get_model creates a SentenceTransformer instance."""
        import sys
        from app.services import embedding

        mock_instance = Mock()
        mock_st_module = Mock()
        mock_st_module.SentenceTransformer.return_value = mock_instance

        with patch.dict(sys.modules, {'sentence_transformers': mock_st_module}):
            model = embedding.get_model()

            mock_st_module.SentenceTransformer.assert_called_once()
            assert model == mock_instance

    def test_get_model_caches_instance(self):
        """Test that get_model returns cached instance on subsequent calls."""
        import sys
        from app.services import embedding

        mock_instance = Mock()
        mock_st_module = Mock()
        mock_st_module.SentenceTransformer.return_value = mock_instance

        with patch.dict(sys.modules, {'sentence_transformers': mock_st_module}):
            model1 = embedding.get_model()
            model2 = embedding.get_model()

            # SentenceTransformer should only be instantiated once
            assert mock_st_module.SentenceTransformer.call_count == 1
            assert model1 is model2


class TestCreateEmbedding:
    """Tests for create_embedding function."""

    @patch('app.services.embedding.get_model')
    def test_create_embedding_basic(self, mock_get_model):
        """Test creating embedding for a simple text."""
        from app.services.embedding import create_embedding

        mock_model = Mock()
        mock_embedding = np.array([0.1, 0.2, 0.3])
        mock_model.encode.return_value = mock_embedding
        mock_get_model.return_value = mock_model

        result = create_embedding("test text")

        mock_model.encode.assert_called_once_with("test text", normalize_embeddings=True)
        assert result == [0.1, 0.2, 0.3]

    @patch('app.services.embedding.get_model')
    def test_create_embedding_empty_string(self, mock_get_model):
        """Test creating embedding for empty string."""
        from app.services.embedding import create_embedding

        mock_model = Mock()
        mock_embedding = np.array([0.0, 0.0, 0.0])
        mock_model.encode.return_value = mock_embedding
        mock_get_model.return_value = mock_model

        result = create_embedding("")

        mock_model.encode.assert_called_once_with("", normalize_embeddings=True)
        assert result == [0.0, 0.0, 0.0]

    @patch('app.services.embedding.get_model')
    def test_create_embedding_long_text(self, mock_get_model):
        """Test creating embedding for long text."""
        from app.services.embedding import create_embedding

        mock_model = Mock()
        mock_embedding = np.array([0.5, 0.6, 0.7])
        mock_model.encode.return_value = mock_embedding
        mock_get_model.return_value = mock_model

        long_text = "test " * 1000
        result = create_embedding(long_text)

        mock_model.encode.assert_called_once_with(long_text, normalize_embeddings=True)
        assert result == [0.5, 0.6, 0.7]


class TestCreateEmbeddingsBatch:
    """Tests for create_embeddings_batch function."""

    @patch('app.services.embedding.get_model')
    def test_create_embeddings_batch_basic(self, mock_get_model):
        """Test creating embeddings for multiple texts."""
        from app.services.embedding import create_embeddings_batch

        mock_model = Mock()
        mock_embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ])
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model

        texts = ["text 1", "text 2"]
        result = create_embeddings_batch(texts)

        mock_model.encode.assert_called_once_with(
            texts,
            normalize_embeddings=True,
            batch_size=32
        )
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @patch('app.services.embedding.get_model')
    def test_create_embeddings_batch_empty_list(self, mock_get_model):
        """Test creating embeddings for empty list."""
        from app.services.embedding import create_embeddings_batch

        mock_model = Mock()
        mock_embeddings = np.array([])
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model

        result = create_embeddings_batch([])

        mock_model.encode.assert_called_once()
        assert result == []

    @patch('app.services.embedding.get_model')
    def test_create_embeddings_batch_large(self, mock_get_model):
        """Test creating embeddings for large batch."""
        from app.services.embedding import create_embeddings_batch

        mock_model = Mock()
        # Create 100 fake embeddings
        mock_embeddings = np.random.rand(100, 384)
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model

        texts = [f"text {i}" for i in range(100)]
        result = create_embeddings_batch(texts)

        mock_model.encode.assert_called_once()
        assert len(result) == 100
        assert all(len(emb) == 384 for emb in result)


class TestGetArticleText:
    """Tests for get_article_text function."""

    def test_get_article_text_title_only(self):
        """Test with title only."""
        from app.services.embedding import get_article_text

        result = get_article_text("Test Title")
        assert result == "Test Title"

    def test_get_article_text_with_none_content(self):
        """Test with None content."""
        from app.services.embedding import get_article_text

        result = get_article_text("Test Title", None)
        assert result == "Test Title"

    def test_get_article_text_with_empty_content(self):
        """Test with empty string content - empty string is falsy."""
        from app.services.embedding import get_article_text

        # Empty string is falsy, so no space is added
        result = get_article_text("Test Title", "")
        assert result == "Test Title"

    def test_get_article_text_with_short_content(self):
        """Test with content shorter than 500 chars."""
        from app.services.embedding import get_article_text

        content = "This is a short article content."
        result = get_article_text("Test Title", content)
        assert result == f"Test Title {content}"

    def test_get_article_text_with_long_content(self):
        """Test with content longer than 500 chars."""
        from app.services.embedding import get_article_text

        content = "a" * 1000
        result = get_article_text("Test Title", content)

        expected = "Test Title " + "a" * 500
        assert result == expected
        assert len(result) == len("Test Title ") + 500

    def test_get_article_text_exactly_500_chars(self):
        """Test with content exactly 500 chars."""
        from app.services.embedding import get_article_text

        content = "b" * 500
        result = get_article_text("Test Title", content)

        expected = "Test Title " + content
        assert result == expected

    def test_get_article_text_with_special_chars(self):
        """Test with special characters in title and content."""
        from app.services.embedding import get_article_text

        title = "Test: Title & More!"
        content = "Content with <html> & special chars: $100"
        result = get_article_text(title, content)

        assert result == f"{title} {content}"
