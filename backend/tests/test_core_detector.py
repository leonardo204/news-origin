"""
Test module for app.core.detector

Tests:
- Empty input handling
- No explosion scenarios
- Single explosion point
- Multiple explosion points
- Explosion range merging
- Threshold calculations (20% min, 5 absolute min)
"""
import pytest
from datetime import datetime, timedelta
from app.core.detector import detect_explosion_points, _merge_ranges


class TestDetectExplosionPoints:
    """Test explosion point detection logic"""

    def test_empty_input(self):
        """Empty published_times list returns empty explosions"""
        explosions = detect_explosion_points([], total_count=0)
        assert explosions == []

    def test_no_explosion_evenly_distributed(self):
        """Articles evenly distributed over time have no explosion"""
        # 10 articles spread over 10 hours (1 per hour)
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        times = [base_time + timedelta(hours=i) for i in range(10)]

        explosions = detect_explosion_points(times, total_count=10)

        # Threshold = max(5, 10 * 0.2) = 5
        # Each hour has only 1 article, so no explosion
        assert explosions == []

    def test_no_explosion_below_threshold(self):
        """Articles below threshold count have no explosion"""
        # 20 articles, but max 4 in any hour (below threshold of 5)
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        times = []
        for hour in range(5):
            for _ in range(4):
                times.append(base_time + timedelta(hours=hour, minutes=15))

        explosions = detect_explosion_points(times, total_count=20)

        # Threshold = max(5, 20 * 0.2) = max(5, 4) = 5
        # Each hour has 4 articles, below threshold
        assert explosions == []

    def test_single_explosion_point(self):
        """Single hour with concentrated articles creates explosion"""
        # 25 articles total: 20 in one hour, rest spread out
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        explosion_time = datetime(2024, 1, 15, 14, 0, 0)

        times = []
        # 20 articles at 14:00
        for _ in range(20):
            times.append(explosion_time)

        # 5 articles spread over other hours
        for i in range(5):
            times.append(base_time + timedelta(hours=i))

        explosions = detect_explosion_points(times, total_count=25)

        # Threshold = max(5, 25 * 0.2) = max(5, 5) = 5
        # 14:00 has 20 articles >= 5
        assert len(explosions) == 1
        assert explosions[0] == (explosion_time, explosion_time + timedelta(hours=1))

    def test_multiple_explosion_points_separate(self):
        """Multiple separate explosion points are detected"""
        # Two explosion windows with gap in between
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        explosion1 = datetime(2024, 1, 15, 14, 0, 0)
        explosion2 = datetime(2024, 1, 15, 18, 0, 0)

        times = []
        # 10 articles at 14:00
        for _ in range(10):
            times.append(explosion1)

        # 10 articles at 18:00
        for _ in range(10):
            times.append(explosion2)

        # 5 articles spread elsewhere
        for i in range(5):
            times.append(base_time + timedelta(hours=i))

        explosions = detect_explosion_points(times, total_count=25)

        # Threshold = max(5, 25 * 0.2) = 5
        assert len(explosions) == 2
        assert explosions[0] == (explosion1, explosion1 + timedelta(hours=1))
        assert explosions[1] == (explosion2, explosion2 + timedelta(hours=1))

    def test_explosion_range_merging_consecutive(self):
        """Consecutive explosion hours are merged into single range"""
        # 14:00, 15:00, 16:00 all have explosions
        base_time = datetime(2024, 1, 15, 14, 0, 0)

        times = []
        # 6 articles at 14:00, 15:00, 16:00 each
        for hour_offset in range(3):
            for _ in range(6):
                times.append(base_time + timedelta(hours=hour_offset))

        explosions = detect_explosion_points(times, total_count=18)

        # Threshold = max(5, 18 * 0.2) = max(5, 3.6) = 5
        # Each hour has 6 >= 5, should merge
        assert len(explosions) == 1
        assert explosions[0] == (
            base_time,
            base_time + timedelta(hours=3),  # 14:00 to 17:00
        )

    def test_explosion_range_merging_overlapping(self):
        """Overlapping explosion ranges are merged"""
        # 14:00-15:00 and 15:00-16:00 should merge to 14:00-16:00
        base_time = datetime(2024, 1, 15, 14, 0, 0)

        times = []
        # Heavy concentration in 14:00 and 15:00
        for _ in range(8):
            times.append(base_time)  # 14:00
        for _ in range(7):
            times.append(base_time + timedelta(hours=1))  # 15:00

        explosions = detect_explosion_points(times, total_count=15)

        # Threshold = max(5, 15 * 0.2) = 5
        assert len(explosions) == 1
        assert explosions[0][0] == base_time
        assert explosions[0][1] == base_time + timedelta(hours=2)

    def test_threshold_calculation_20_percent(self):
        """Threshold is 20% of total when that exceeds 5"""
        base_time = datetime(2024, 1, 15, 14, 0, 0)

        times = []
        # 100 articles total, 25 in one hour (25% > 20%)
        for _ in range(25):
            times.append(base_time)

        # 75 articles spread over 10 hours
        for i in range(75):
            times.append(base_time + timedelta(hours=i % 10 + 2))

        explosions = detect_explosion_points(times, total_count=100)

        # Threshold = max(5, 100 * 0.2) = 20
        # 14:00 has 25 articles >= 20
        assert len(explosions) >= 1
        assert explosions[0][0] == base_time

    def test_threshold_calculation_minimum_5(self):
        """Threshold is minimum 5 even when 20% is less"""
        base_time = datetime(2024, 1, 15, 14, 0, 0)

        times = []
        # 20 articles total, 5 in one hour
        for _ in range(5):
            times.append(base_time)

        # 15 articles spread elsewhere
        for i in range(15):
            times.append(base_time + timedelta(hours=i + 1))

        explosions = detect_explosion_points(times, total_count=20)

        # Threshold = max(5, 20 * 0.2) = max(5, 4) = 5
        # 14:00 has exactly 5 articles
        assert len(explosions) == 1
        assert explosions[0][0] == base_time

    def test_none_published_times_filtered(self):
        """None values in published_times are filtered out"""
        base_time = datetime(2024, 1, 15, 14, 0, 0)

        times = [base_time] * 10 + [None] * 5

        explosions = detect_explosion_points(times, total_count=15)

        # Should work with only valid times
        # Threshold = max(5, 15 * 0.2) = 5
        # 10 articles at base_time >= 5
        assert len(explosions) == 1

    def test_custom_window_hours(self):
        """Custom window_hours parameter affects explosion ranges"""
        base_time = datetime(2024, 1, 15, 14, 0, 0)

        times = [base_time] * 10

        explosions = detect_explosion_points(times, total_count=10, window_hours=2)

        # Threshold = max(5, 10 * 0.2) = 5
        assert len(explosions) == 1
        assert explosions[0] == (base_time, base_time + timedelta(hours=2))

    def test_korean_news_realistic_scenario(self):
        """Realistic Korean news explosion scenario"""
        # Breaking news at 14:00: 속보 발생
        breaking_time = datetime(2024, 1, 15, 14, 0, 0)

        times = []
        # 30 articles in first hour (14:00-14:59)
        for minute in range(30):
            times.append(breaking_time + timedelta(minutes=minute * 2))

        # 20 articles in second hour (15:00-15:59)
        for minute in range(20):
            times.append(breaking_time + timedelta(hours=1, minutes=minute * 3))

        # 10 articles spread over next 5 hours
        for hour in range(2, 7):
            for _ in range(2):
                times.append(breaking_time + timedelta(hours=hour))

        explosions = detect_explosion_points(times, total_count=60)

        # Threshold = max(5, 60 * 0.2) = 12
        # Should detect explosion at 14:00 and 15:00, merged into one range
        assert len(explosions) >= 1
        assert explosions[0][0] == breaking_time


class TestMergeRanges:
    """Test time range merging helper function"""

    def test_empty_ranges(self):
        """Empty input returns empty output"""
        assert _merge_ranges([]) == []

    def test_single_range(self):
        """Single range is returned as-is"""
        start = datetime(2024, 1, 15, 14, 0, 0)
        end = datetime(2024, 1, 15, 15, 0, 0)

        result = _merge_ranges([(start, end)])

        assert result == [(start, end)]

    def test_non_overlapping_ranges(self):
        """Non-overlapping ranges remain separate"""
        range1 = (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 15, 0, 0))
        range2 = (datetime(2024, 1, 15, 16, 0, 0), datetime(2024, 1, 15, 17, 0, 0))

        result = _merge_ranges([range1, range2])

        assert len(result) == 2
        assert result == [range1, range2]

    def test_overlapping_ranges(self):
        """Overlapping ranges are merged"""
        range1 = (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 15, 30, 0))
        range2 = (datetime(2024, 1, 15, 15, 0, 0), datetime(2024, 1, 15, 16, 0, 0))

        result = _merge_ranges([range1, range2])

        assert len(result) == 1
        assert result[0] == (
            datetime(2024, 1, 15, 14, 0, 0),
            datetime(2024, 1, 15, 16, 0, 0),
        )

    def test_adjacent_ranges(self):
        """Adjacent ranges (end == next start) are merged"""
        range1 = (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 15, 0, 0))
        range2 = (datetime(2024, 1, 15, 15, 0, 0), datetime(2024, 1, 15, 16, 0, 0))

        result = _merge_ranges([range1, range2])

        assert len(result) == 1
        assert result[0] == (
            datetime(2024, 1, 15, 14, 0, 0),
            datetime(2024, 1, 15, 16, 0, 0),
        )

    def test_multiple_overlapping_ranges(self):
        """Multiple overlapping ranges merge into one"""
        ranges = [
            (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 15, 0, 0)),
            (datetime(2024, 1, 15, 14, 30, 0), datetime(2024, 1, 15, 15, 30, 0)),
            (datetime(2024, 1, 15, 15, 0, 0), datetime(2024, 1, 15, 16, 0, 0)),
        ]

        result = _merge_ranges(ranges)

        assert len(result) == 1
        assert result[0] == (
            datetime(2024, 1, 15, 14, 0, 0),
            datetime(2024, 1, 15, 16, 0, 0),
        )

    def test_mixed_overlapping_and_separate(self):
        """Mix of overlapping and separate ranges"""
        ranges = [
            (datetime(2024, 1, 15, 10, 0, 0), datetime(2024, 1, 15, 11, 0, 0)),
            (datetime(2024, 1, 15, 10, 30, 0), datetime(2024, 1, 15, 11, 30, 0)),
            (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 15, 0, 0)),
            (datetime(2024, 1, 15, 18, 0, 0), datetime(2024, 1, 15, 19, 0, 0)),
        ]

        result = _merge_ranges(ranges)

        assert len(result) == 3
        assert result[0] == (
            datetime(2024, 1, 15, 10, 0, 0),
            datetime(2024, 1, 15, 11, 30, 0),
        )
        assert result[1] == (
            datetime(2024, 1, 15, 14, 0, 0),
            datetime(2024, 1, 15, 15, 0, 0),
        )
        assert result[2] == (
            datetime(2024, 1, 15, 18, 0, 0),
            datetime(2024, 1, 15, 19, 0, 0),
        )

    def test_subset_range_absorbed(self):
        """Smaller range completely inside larger range is absorbed"""
        ranges = [
            (datetime(2024, 1, 15, 14, 0, 0), datetime(2024, 1, 15, 17, 0, 0)),
            (datetime(2024, 1, 15, 15, 0, 0), datetime(2024, 1, 15, 16, 0, 0)),
        ]

        result = _merge_ranges(ranges)

        assert len(result) == 1
        assert result[0] == (
            datetime(2024, 1, 15, 14, 0, 0),
            datetime(2024, 1, 15, 17, 0, 0),
        )
