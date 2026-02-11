"""
Test module for app.core.timeline

Tests:
- build_timeline with origin only
- build_timeline with mixed categories
- lifecycle stage determination
- parent inference for each category
- handling None published_at values
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from app.core.timeline import (
    build_timeline,
    _determine_lifecycle_stage,
    _infer_parent,
)


class TestBuildTimeline:
    """Test timeline construction from origin and similar articles"""

    def test_build_timeline_origin_only(self):
        """Timeline with only origin article"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        timeline = build_timeline(origin, [])

        assert len(timeline) == 1
        assert timeline[0]["article_id"] == "origin_001"
        assert timeline[0]["similarity_score"] == 1.0
        assert timeline[0]["similarity_category"] == "same"
        assert timeline[0]["lifecycle_stage"] == "origin"
        assert timeline[0]["parent_article_id"] is None
        assert timeline[0]["is_origin"] is True

    def test_build_timeline_with_same_category(self):
        """Timeline with same category articles"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        similar = [
            {
                "id": "similar_001",
                "score": 0.95,
                "category": "same",
                "published_at": datetime(2024, 1, 15, 10, 30, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        assert len(timeline) == 2
        # Origin entry
        assert timeline[0]["is_origin"] is True

        # Same category entry
        assert timeline[1]["article_id"] == "similar_001"
        assert timeline[1]["similarity_category"] == "same"
        assert timeline[1]["parent_article_id"] == "origin_001"
        assert timeline[1]["is_origin"] is False

    def test_build_timeline_with_derivative_category(self):
        """Timeline with derivative category articles"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        similar = [
            {
                "id": "deriv_001",
                "score": 0.80,
                "category": "derivative",
                "published_at": datetime(2024, 1, 15, 11, 0, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        assert len(timeline) == 2
        assert timeline[1]["article_id"] == "deriv_001"
        assert timeline[1]["similarity_category"] == "derivative"
        assert timeline[1]["parent_article_id"] == "origin_001"

    def test_build_timeline_with_related_category(self):
        """Timeline with related category articles following chain"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        similar = [
            {
                "id": "related_001",
                "score": 0.65,
                "category": "related",
                "published_at": datetime(2024, 1, 15, 11, 0, 0),
            },
            {
                "id": "related_002",
                "score": 0.62,
                "category": "related",
                "published_at": datetime(2024, 1, 15, 12, 0, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        assert len(timeline) == 3
        # First related points to origin
        assert timeline[1]["article_id"] == "related_001"
        assert timeline[1]["parent_article_id"] == "origin_001"

        # Second related points to previous related (chain)
        assert timeline[2]["article_id"] == "related_002"
        assert timeline[2]["parent_article_id"] == "related_001"

    def test_build_timeline_with_isolated_category(self):
        """Timeline with isolated category articles have no parent"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        similar = [
            {
                "id": "isolated_001",
                "score": 0.55,
                "category": "isolated",
                "published_at": datetime(2024, 1, 15, 11, 0, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        assert len(timeline) == 2
        assert timeline[1]["article_id"] == "isolated_001"
        assert timeline[1]["similarity_category"] == "isolated"
        assert timeline[1]["parent_article_id"] is None
        assert timeline[1]["lifecycle_stage"] == "isolated"

    def test_build_timeline_mixed_categories(self):
        """Timeline with mixed similarity categories"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        similar = [
            {
                "id": "same_001",
                "score": 0.95,
                "category": "same",
                "published_at": datetime(2024, 1, 15, 10, 15, 0),
            },
            {
                "id": "deriv_001",
                "score": 0.80,
                "category": "derivative",
                "published_at": datetime(2024, 1, 15, 10, 30, 0),
            },
            {
                "id": "related_001",
                "score": 0.65,
                "category": "related",
                "published_at": datetime(2024, 1, 15, 11, 0, 0),
            },
            {
                "id": "isolated_001",
                "score": 0.55,
                "category": "isolated",
                "published_at": datetime(2024, 1, 15, 12, 0, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        assert len(timeline) == 5
        assert timeline[1]["parent_article_id"] == "origin_001"  # same -> origin
        assert timeline[2]["parent_article_id"] == "origin_001"  # derivative -> origin
        assert timeline[3]["parent_article_id"] == "deriv_001"  # related -> previous
        assert timeline[4]["parent_article_id"] is None  # isolated -> None

    def test_build_timeline_sorts_by_time(self):
        """Timeline entries are sorted by published_at"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        # Intentionally unsorted input
        similar = [
            {
                "id": "article_3",
                "score": 0.80,
                "category": "derivative",
                "published_at": datetime(2024, 1, 15, 14, 0, 0),
            },
            {
                "id": "article_1",
                "score": 0.90,
                "category": "same",
                "published_at": datetime(2024, 1, 15, 10, 30, 0),
            },
            {
                "id": "article_2",
                "score": 0.85,
                "category": "derivative",
                "published_at": datetime(2024, 1, 15, 12, 0, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        # Should be sorted by time
        assert timeline[1]["article_id"] == "article_1"  # 10:30
        assert timeline[2]["article_id"] == "article_2"  # 12:00
        assert timeline[3]["article_id"] == "article_3"  # 14:00

    def test_build_timeline_with_none_published_at(self):
        """Timeline handles None published_at values"""
        origin = {
            "id": "origin_001",
            "title": "원본 기사",
            "published_at": datetime(2024, 1, 15, 10, 0, 0),
        }

        similar = [
            {
                "id": "no_time",
                "score": 0.80,
                "category": "derivative",
                "published_at": None,
            },
            {
                "id": "has_time",
                "score": 0.85,
                "category": "derivative",
                "published_at": datetime(2024, 1, 15, 11, 0, 0),
            },
        ]

        timeline = build_timeline(origin, similar)

        # Articles with None time should sort to end
        assert len(timeline) == 3
        assert timeline[1]["article_id"] == "has_time"
        assert timeline[2]["article_id"] == "no_time"


class TestDetermineLifecycleStage:
    """Test lifecycle stage determination logic"""

    def test_isolated_category_always_isolated(self):
        """Isolated category always returns isolated stage"""
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 15, 10, 0, 0),
            origin_time=datetime(2024, 1, 15, 9, 0, 0),
            explosion_ranges=[],
            category="isolated",
            entry_index=1,
        )

        assert stage == "isolated"

    def test_none_published_at_returns_spread(self):
        """None published_at returns spread stage"""
        stage = _determine_lifecycle_stage(
            published_at=None,
            origin_time=datetime(2024, 1, 15, 9, 0, 0),
            explosion_ranges=[],
            category="derivative",
            entry_index=1,
        )

        assert stage == "spread"

    def test_none_origin_time_returns_spread(self):
        """None origin_time returns spread stage"""
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 15, 10, 0, 0),
            origin_time=None,
            explosion_ranges=[],
            category="derivative",
            entry_index=1,
        )

        assert stage == "spread"

    def test_explosion_stage_in_range(self):
        """Article in explosion range returns explosion stage"""
        explosion_ranges = [
            (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 16, 0, 0)),
        ]

        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 15, 15, 0, 0),
            origin_time=datetime(2024, 1, 15, 10, 0, 0),
            explosion_ranges=explosion_ranges,
            category="derivative",
            entry_index=10,
        )

        assert stage == "explosion"

    def test_spread_stage_within_5_entries(self):
        """Entry index <= 5 returns spread stage"""
        for index in range(1, 6):
            stage = _determine_lifecycle_stage(
                published_at=datetime(2024, 1, 15, 10, 0, 0),
                origin_time=datetime(2024, 1, 15, 9, 0, 0),
                explosion_ranges=[],
                category="derivative",
                entry_index=index,
            )

            assert stage == "spread", f"Failed at index {index}"

    def test_spread_stage_within_6_hours(self):
        """Article within 6 hours of origin returns spread stage"""
        origin_time = datetime(2024, 1, 15, 10, 0, 0)

        # 5.5 hours after origin
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 15, 15, 30, 0),
            origin_time=origin_time,
            explosion_ranges=[],
            category="derivative",
            entry_index=10,
        )

        assert stage == "spread"

    def test_sustained_stage_between_6_and_48_hours(self):
        """Article between 6 and 48 hours returns sustained stage"""
        origin_time = datetime(2024, 1, 15, 10, 0, 0)

        # 24 hours after origin
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 16, 10, 0, 0),
            origin_time=origin_time,
            explosion_ranges=[],
            category="derivative",
            entry_index=10,
        )

        assert stage == "sustained"

    def test_fadeout_stage_after_48_hours(self):
        """Article after 48 hours returns fadeout stage"""
        origin_time = datetime(2024, 1, 15, 10, 0, 0)

        # 50 hours after origin
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 17, 12, 0, 0),
            origin_time=origin_time,
            explosion_ranges=[],
            category="derivative",
            entry_index=10,
        )

        assert stage == "fadeout"

    def test_lifecycle_priority_explosion_over_time(self):
        """Explosion stage takes priority over time-based stages"""
        origin_time = datetime(2024, 1, 15, 10, 0, 0)
        explosion_ranges = [
            (datetime(2024, 1, 17, 10, 0, 0), datetime(2024, 1, 17, 12, 0, 0)),
        ]

        # 50 hours after origin (would be fadeout), but in explosion range
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 17, 11, 0, 0),
            origin_time=origin_time,
            explosion_ranges=explosion_ranges,
            category="derivative",
            entry_index=50,
        )

        assert stage == "explosion"

    def test_lifecycle_priority_entry_index_over_time(self):
        """Entry index <= 5 takes priority over elapsed time"""
        origin_time = datetime(2024, 1, 15, 10, 0, 0)

        # 10 hours after origin (would be sustained), but entry_index <= 5
        stage = _determine_lifecycle_stage(
            published_at=datetime(2024, 1, 15, 20, 0, 0),
            origin_time=origin_time,
            explosion_ranges=[],
            category="derivative",
            entry_index=3,
        )

        assert stage == "spread"


class TestInferParent:
    """Test parent article inference logic"""

    def test_isolated_has_no_parent(self):
        """Isolated category articles have no parent"""
        parent = _infer_parent(
            article={"id": "art_001"},
            existing_entries=[],
            origin_id="origin_001",
            category="isolated",
        )

        assert parent is None

    def test_same_category_parent_is_origin(self):
        """Same category articles point to origin"""
        parent = _infer_parent(
            article={"id": "art_001"},
            existing_entries=[],
            origin_id="origin_001",
            category="same",
        )

        assert parent == "origin_001"

    def test_derivative_category_parent_is_origin(self):
        """Derivative category articles point to origin"""
        parent = _infer_parent(
            article={"id": "art_001"},
            existing_entries=[],
            origin_id="origin_001",
            category="derivative",
        )

        assert parent == "origin_001"

    def test_related_category_parent_is_last_entry(self):
        """Related category articles point to most recent entry"""
        existing_entries = [
            {"article_id": "origin_001"},
            {"article_id": "art_001"},
            {"article_id": "art_002"},
        ]

        parent = _infer_parent(
            article={"id": "art_003"},
            existing_entries=existing_entries,
            origin_id="origin_001",
            category="related",
        )

        assert parent == "art_002"

    def test_related_category_empty_entries_defaults_origin(self):
        """Related category with no existing entries defaults to origin"""
        parent = _infer_parent(
            article={"id": "art_001"},
            existing_entries=[],
            origin_id="origin_001",
            category="related",
        )

        assert parent == "origin_001"

    def test_related_category_builds_chain(self):
        """Related articles build a chain from origin"""
        entries = [{"article_id": "origin_001"}]

        # First related
        parent1 = _infer_parent(
            article={"id": "related_001"},
            existing_entries=entries,
            origin_id="origin_001",
            category="related",
        )
        assert parent1 == "origin_001"

        # Add to entries
        entries.append({"article_id": "related_001"})

        # Second related
        parent2 = _infer_parent(
            article={"id": "related_002"},
            existing_entries=entries,
            origin_id="origin_001",
            category="related",
        )
        assert parent2 == "related_001"

        # Add to entries
        entries.append({"article_id": "related_002"})

        # Third related
        parent3 = _infer_parent(
            article={"id": "related_003"},
            existing_entries=entries,
            origin_id="origin_001",
            category="related",
        )
        assert parent3 == "related_002"

    def test_mixed_categories_parent_inference(self):
        """Mixed categories follow correct parent inference rules"""
        entries = [
            {"article_id": "origin_001"},
            {"article_id": "same_001"},  # same -> origin
            {"article_id": "deriv_001"},  # derivative -> origin
        ]

        # Same category always points to origin
        parent_same = _infer_parent(
            article={"id": "same_002"},
            existing_entries=entries,
            origin_id="origin_001",
            category="same",
        )
        assert parent_same == "origin_001"

        # Related points to last entry
        parent_related = _infer_parent(
            article={"id": "related_001"},
            existing_entries=entries,
            origin_id="origin_001",
            category="related",
        )
        assert parent_related == "deriv_001"

        # Isolated has no parent
        parent_isolated = _infer_parent(
            article={"id": "isolated_001"},
            existing_entries=entries,
            origin_id="origin_001",
            category="isolated",
        )
        assert parent_isolated is None

    def test_korean_realistic_news_chain(self):
        """Realistic Korean news propagation chain"""
        # 속보 → 단독보도 → 후속보도 체인
        entries = [{"article_id": "origin_breaking"}]

        # 동일 매체 재보도 (same)
        parent1 = _infer_parent(
            article={"id": "same_repost"},
            existing_entries=entries,
            origin_id="origin_breaking",
            category="same",
        )
        assert parent1 == "origin_breaking"

        entries.append({"article_id": "same_repost"})

        # 타 매체 인용보도 (derivative)
        parent2 = _infer_parent(
            article={"id": "deriv_citation"},
            existing_entries=entries,
            origin_id="origin_breaking",
            category="derivative",
        )
        assert parent2 == "origin_breaking"

        entries.append({"article_id": "deriv_citation"})

        # 후속 분석기사 (related)
        parent3 = _infer_parent(
            article={"id": "related_analysis"},
            existing_entries=entries,
            origin_id="origin_breaking",
            category="related",
        )
        assert parent3 == "deriv_citation"

        entries.append({"article_id": "related_analysis"})

        # 무관한 기사 (isolated)
        parent4 = _infer_parent(
            article={"id": "isolated_unrelated"},
            existing_entries=entries,
            origin_id="origin_breaking",
            category="isolated",
        )
        assert parent4 is None
