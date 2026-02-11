"""Pydantic schema validation tests"""
import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.article import ArticleBase, ArticleResponse
from app.schemas.timeline import (
    TrackInput,
    TrackResponse,
    TrackCandidate,
    ConfirmInput,
    ConfirmResponse,
    TrackingStatus,
    GraphNode,
    GraphEdge,
    TimelineItem,
    DensityPoint,
    ExplosionPoint,
    LifecycleSummary,
    TimelineResponse,
)
from app.schemas.search import TrendItem, PopularSearch, StatsOverview


def test_article_base():
    article = ArticleBase(url="https://example.com", title="Test")
    assert article.url == "https://example.com"
    assert article.publisher is None


def test_track_input():
    track = TrackInput(text="https://example.com/article")
    assert track.text == "https://example.com/article"


def test_track_response_url():
    article = ArticleResponse(
        id=uuid.uuid4(),
        url="https://example.com",
        title="Test",
        created_at=datetime.now(timezone.utc),
    )
    resp = TrackResponse(input_type="url", article=article)
    assert resp.input_type == "url"
    assert resp.article is not None
    assert resp.candidates == []


def test_track_response_title():
    candidates = [
        TrackCandidate(title="News 1", url="https://example.com/1"),
        TrackCandidate(title="News 2", url="https://example.com/2"),
    ]
    resp = TrackResponse(input_type="title", candidates=candidates)
    assert resp.input_type == "title"
    assert len(resp.candidates) == 2
    assert resp.article is None


def test_confirm_input():
    aid = uuid.uuid4()
    confirm = ConfirmInput(article_id=aid)
    assert confirm.article_id == aid


def test_tracking_status_defaults():
    tid = uuid.uuid4()
    status = TrackingStatus(tracking_id=tid, status="pending")
    assert status.progress == 0
    assert status.total_articles == 0
    assert status.message == ""


def test_graph_node():
    node = GraphNode(id="abc", title="Test Node")
    assert node.is_origin is False
    assert node.similarity_score == 0.0


def test_lifecycle_summary_defaults():
    summary = LifecycleSummary()
    assert summary.total_articles == 0
    assert summary.stage_counts == {}


def test_timeline_response():
    article = ArticleResponse(
        id=uuid.uuid4(),
        url="https://example.com",
        title="Origin",
        created_at=datetime.now(timezone.utc),
    )
    resp = TimelineResponse(
        tracking_id=uuid.uuid4(),
        origin_article=article,
    )
    assert resp.graph.nodes == []
    assert resp.timeline == []
    assert resp.density == []


def test_trend_item():
    trend = TrendItem(title="Hot News", tracking_count=10)
    assert trend.latest_tracking_id is None


def test_popular_search():
    ps = PopularSearch(query="test", count=5)
    assert ps.query == "test"


def test_stats_overview_defaults():
    stats = StatsOverview()
    assert stats.total_trackings == 0
    assert stats.total_articles == 0
    assert stats.active_trackings == 0
