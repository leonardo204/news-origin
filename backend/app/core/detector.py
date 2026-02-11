"""
# detector.py - Explosion Point Detector
# Version: 0.1.0
# Description: 뉴스 폭발 시점 감지 (단시간 다수 보도 감지)
# Changes:
#   - 0.1.0: 시간 윈도우 기반 폭발 감지
"""

from collections import Counter
from datetime import datetime, timedelta


def detect_explosion_points(
    published_times: list[datetime],
    total_count: int,
    window_hours: int = 1,
) -> list[tuple[datetime, datetime]]:
    """
    폭발 시점 감지

    [BUSINESS LOGIC - DO NOT MODIFY]
    폭발 판정 기준:
    - 동적 임계값: 전체 기사의 20% 이상이 1시간에 집중
    - 최소 임계값: 5건 이상
    - 윈도우: 1시간 단위

    Args:
        published_times: 기사 발행 시간 목록
        total_count: 전체 기사 수
        window_hours: 시간 윈도우 (기본 1시간)

    Returns:
        폭발 구간 목록 [(start, end), ...]
    """
    if not published_times:
        return []

    # 동적 임계값: 전체의 20%, 최소 5건
    threshold = max(5, int(total_count * 0.2))

    # 시간 윈도우별 카운트
    hour_counts: Counter[datetime] = Counter()
    for t in published_times:
        if t:
            hour = t.replace(minute=0, second=0, microsecond=0)
            hour_counts[hour] += 1

    # 임계값 초과 구간 추출
    explosions = []
    for hour, count in sorted(hour_counts.items()):
        if count >= threshold:
            explosions.append((
                hour,
                hour + timedelta(hours=window_hours),
            ))

    # 연속 구간 병합
    return _merge_ranges(explosions)


def _merge_ranges(
    ranges: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """연속/중첩 시간 구간 병합"""
    if not ranges:
        return []

    merged = [ranges[0]]
    for start, end in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged
