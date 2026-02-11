"""Unit tests for vector_store service."""
import pytest
from unittest.mock import Mock, patch
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client import models


@pytest.fixture(autouse=True)
def reset_global_client():
    """Reset the global _client variable before each test."""
    from app.services import vector_store
    vector_store._client = None
    yield
    vector_store._client = None


@pytest.fixture
def mock_qdrant_client():
    """Mock QdrantClient."""
    mock_client = Mock()
    mock_client.get_collection = Mock()
    mock_client.create_collection = Mock()
    mock_client.upsert = Mock()
    mock_client.search = Mock()
    return mock_client


class TestGetQdrantClient:
    """Tests for get_qdrant_client function."""

    @patch('app.services.vector_store.QdrantClient')
    @patch('app.services.vector_store.settings')
    def test_get_qdrant_client_creates_instance(self, mock_settings, mock_qdrant_class):
        """Test that get_qdrant_client creates a QdrantClient instance."""
        from app.services.vector_store import get_qdrant_client

        mock_settings.qdrant_host = "localhost"
        mock_settings.qdrant_port = 6333
        mock_instance = Mock()
        mock_qdrant_class.return_value = mock_instance

        client = get_qdrant_client()

        mock_qdrant_class.assert_called_once_with(
            host="localhost",
            port=6333,
            timeout=30
        )
        assert client == mock_instance

    @patch('app.services.vector_store.QdrantClient')
    @patch('app.services.vector_store.settings')
    def test_get_qdrant_client_caches_instance(self, mock_settings, mock_qdrant_class):
        """Test that get_qdrant_client returns cached instance."""
        from app.services.vector_store import get_qdrant_client

        mock_settings.qdrant_host = "localhost"
        mock_settings.qdrant_port = 6333
        mock_instance = Mock()
        mock_qdrant_class.return_value = mock_instance

        client1 = get_qdrant_client()
        client2 = get_qdrant_client()

        # QdrantClient should only be instantiated once
        assert mock_qdrant_class.call_count == 1
        assert client1 == client2


class TestEnsureCollection:
    """Tests for ensure_collection function."""

    @pytest.mark.anyio
    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    async def test_ensure_collection_already_exists(self, mock_settings, mock_get_client):
        """Test when collection already exists."""
        from app.services.vector_store import ensure_collection

        mock_settings.qdrant_collection = "test_articles"
        mock_settings.embedding_dimension = 768
        mock_client = Mock()
        mock_client.get_collection.return_value = Mock()  # Collection exists
        mock_get_client.return_value = mock_client

        await ensure_collection()

        mock_client.get_collection.assert_called_once_with("test_articles")
        mock_client.create_collection.assert_not_called()

    @pytest.mark.anyio
    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    async def test_ensure_collection_creates_new(self, mock_settings, mock_get_client):
        """Test creating new collection when it doesn't exist."""
        from app.services.vector_store import ensure_collection

        mock_settings.qdrant_collection = "test_articles"
        mock_settings.embedding_dimension = 768
        mock_client = Mock()
        # Simulate collection not existing by raising Exception (not UnexpectedResponse)
        mock_client.get_collection.side_effect = Exception("Collection not found")
        mock_get_client.return_value = mock_client

        await ensure_collection()

        mock_client.get_collection.assert_called_once_with("test_articles")
        mock_client.create_collection.assert_called_once()

        # Verify collection creation parameters
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs["collection_name"] == "test_articles"


class TestUpsertEmbedding:
    """Tests for upsert_embedding function."""

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    @patch('app.services.vector_store.uuid')
    def test_upsert_embedding_basic(self, mock_uuid, mock_settings, mock_get_client):
        """Test basic embedding upsert."""
        from app.services.vector_store import upsert_embedding

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Mock UUID
        mock_uuid.uuid4.return_value = Mock(__str__=lambda _: "abc-123-def")

        article_id = "article-42"
        embedding = [0.1, 0.2, 0.3]
        payload = {"title": "Test"}

        result = upsert_embedding(article_id, embedding, payload)

        mock_client.upsert.assert_called_once()
        call_kwargs = mock_client.upsert.call_args[1]
        assert call_kwargs["collection_name"] == "test_articles"
        assert len(call_kwargs["points"]) == 1
        point = call_kwargs["points"][0]
        assert point.id == "abc-123-def"
        assert point.vector == embedding
        assert point.payload["article_id"] == article_id
        assert point.payload["title"] == "Test"
        assert result == "abc-123-def"

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    @patch('app.services.vector_store.uuid')
    def test_upsert_embedding_no_payload(self, mock_uuid, mock_settings, mock_get_client):
        """Test upsert with no additional payload."""
        from app.services.vector_store import upsert_embedding

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        mock_uuid.uuid4.return_value = Mock(__str__=lambda _: "def-456")

        article_id = "article-99"
        embedding = [0.5, 0.6]

        result = upsert_embedding(article_id, embedding, None)

        mock_client.upsert.assert_called_once()
        call_kwargs = mock_client.upsert.call_args[1]
        point = call_kwargs["points"][0]
        assert point.payload == {"article_id": article_id}
        assert result == "def-456"

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    @patch('app.services.vector_store.uuid')
    def test_upsert_embedding_exception(self, mock_uuid, mock_settings, mock_get_client):
        """Test exception handling during upsert."""
        from app.services.vector_store import upsert_embedding

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_client.upsert.side_effect = Exception("Upsert failed")
        mock_get_client.return_value = mock_client

        with pytest.raises(Exception, match="Upsert failed"):
            upsert_embedding("1", [0.1, 0.2], {})


class TestSearchSimilar:
    """Tests for search_similar function."""

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    def test_search_similar_basic(self, mock_settings, mock_get_client):
        """Test basic similarity search."""
        from app.services.vector_store import search_similar

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()

        # Mock search results
        mock_result1 = Mock()
        mock_result1.id = "point1"
        mock_result1.score = 0.9
        mock_result1.payload = {"article_id": 1, "title": "Article 1"}

        mock_result2 = Mock()
        mock_result2.id = "point2"
        mock_result2.score = 0.8
        mock_result2.payload = {"article_id": 2, "title": "Article 2"}

        mock_client.search.return_value = [mock_result1, mock_result2]
        mock_get_client.return_value = mock_client

        embedding = [0.1, 0.2, 0.3]
        results = search_similar(embedding, limit=50, score_threshold=0.5)

        mock_client.search.assert_called_once_with(
            collection_name="test_articles",
            query_vector=embedding,
            limit=50,
            score_threshold=0.5,
            query_filter=None
        )

        assert len(results) == 2
        assert results[0] == {
            "id": "point1",
            "score": 0.9,
            "payload": {"article_id": 1, "title": "Article 1"}
        }
        assert results[1] == {
            "id": "point2",
            "score": 0.8,
            "payload": {"article_id": 2, "title": "Article 2"}
        }

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    def test_search_similar_with_filter(self, mock_settings, mock_get_client):
        """Test search with filter conditions."""
        from app.services.vector_store import search_similar

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        embedding = [0.1, 0.2]
        filter_conditions = {"source": "BBC"}

        search_similar(embedding, limit=10, filter_conditions=filter_conditions)

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["query_filter"] is not None

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    def test_search_similar_empty_results(self, mock_settings, mock_get_client):
        """Test search with no results."""
        from app.services.vector_store import search_similar

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        results = search_similar([0.1, 0.2])

        assert results == []

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    def test_search_similar_custom_threshold(self, mock_settings, mock_get_client):
        """Test search with custom score threshold."""
        from app.services.vector_store import search_similar

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        search_similar([0.1], limit=20, score_threshold=0.75)

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["score_threshold"] == 0.75
        assert call_kwargs["limit"] == 20

    @patch('app.services.vector_store.get_qdrant_client')
    @patch('app.services.vector_store.settings')
    def test_search_similar_exception(self, mock_settings, mock_get_client):
        """Test exception handling during search."""
        from app.services.vector_store import search_similar

        mock_settings.qdrant_collection = "test_articles"
        mock_client = Mock()
        mock_client.search.side_effect = Exception("Search failed")
        mock_get_client.return_value = mock_client

        with pytest.raises(Exception, match="Search failed"):
            search_similar([0.1, 0.2])
