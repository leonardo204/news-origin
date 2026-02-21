"""
# alert_detector.py - System Alert Detector
# Version: 0.1.0
# Description: 시스템 이상 감지 → 비정기 알림 리포트 트리거
"""

import logging
from datetime import datetime, timedelta, timezone

import psutil
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.admin_report import AdminReport
from app.models.request_log import RequestLog

logger = logging.getLogger(__name__)


async def _recently_alerted(session: AsyncSession, category: str, cooldown_min: int) -> bool:
    """쿨다운 내 동일 카테고리 알림이 있는지 확인"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_min)
    result = (await session.execute(
        select(func.count(AdminReport.id)).where(
            AdminReport.report_type == "alert",
            AdminReport.category == category,
            AdminReport.created_at >= cutoff,
        )
    )).scalar() or 0
    return result > 0


async def check_all_alerts(session: AsyncSession) -> list[dict]:
    """모든 알림 조건 확인, 트리거된 알림 목록 반환"""
    settings = get_settings()
    cooldown = settings.alert_cooldown_minutes
    alerts: list[dict] = []

    # ── 1. 에러율 급증 ──
    try:
        if not await _recently_alerted(session, "traffic", cooldown):
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            total = (await session.execute(
                select(func.count(RequestLog.id)).where(
                    RequestLog.created_at >= one_hour_ago
                )
            )).scalar() or 0

            errors = (await session.execute(
                select(func.count(RequestLog.id)).where(
                    RequestLog.created_at >= one_hour_ago,
                    RequestLog.status_code >= 500,
                )
            )).scalar() or 0

            if total >= 10:  # 최소 요청 수 충족 시만 판단
                error_rate = errors / total * 100
                if error_rate >= settings.alert_error_rate_threshold:
                    alerts.append({
                        "category": "traffic",
                        "severity": "critical" if error_rate >= 30 else "warning",
                        "title": f"서버 에러율 급증: {error_rate:.1f}% (최근 1시간)",
                        "summary": f"최근 1시간 동안 {total}건 중 {errors}건이 5xx 에러입니다.\n에러율: {error_rate:.1f}% (임계치: {settings.alert_error_rate_threshold}%)",
                        "details": {
                            "error_rate": round(error_rate, 1),
                            "total_requests": total,
                            "error_count": errors,
                            "threshold": settings.alert_error_rate_threshold,
                            "period": "1h",
                        },
                    })
    except Exception as e:
        logger.warning(f"에러율 알림 체크 실패: {e}")

    # ── 2. 트래픽 급증 ──
    try:
        if not await _recently_alerted(session, "traffic_spike", cooldown):
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            prev_start = datetime.now(timezone.utc) - timedelta(hours=25)
            prev_end = datetime.now(timezone.utc) - timedelta(hours=1)

            current_count = (await session.execute(
                select(func.count(RequestLog.id)).where(
                    RequestLog.created_at >= one_hour_ago
                )
            )).scalar() or 0

            prev_avg = (await session.execute(
                select(func.count(RequestLog.id)).where(
                    RequestLog.created_at >= prev_start,
                    RequestLog.created_at < prev_end,
                )
            )).scalar() or 0
            # 24시간의 평균 시간당 요청
            prev_hourly_avg = prev_avg / 24 if prev_avg > 0 else 0

            if prev_hourly_avg >= 5 and current_count >= prev_hourly_avg * settings.alert_traffic_spike_multiplier:
                multiplier = round(current_count / prev_hourly_avg, 1)
                alerts.append({
                    "category": "traffic_spike",
                    "severity": "warning",
                    "title": f"트래픽 급증 감지: {multiplier}배 (최근 1시간)",
                    "summary": f"최근 1시간 요청: {current_count}건\n24시간 평균: {prev_hourly_avg:.0f}건/시간\n급증 배율: {multiplier}배 (임계치: {settings.alert_traffic_spike_multiplier}배)",
                    "details": {
                        "current_hourly": current_count,
                        "avg_hourly": round(prev_hourly_avg, 1),
                        "multiplier": multiplier,
                        "threshold": settings.alert_traffic_spike_multiplier,
                    },
                })
    except Exception as e:
        logger.warning(f"트래픽 급증 알림 체크 실패: {e}")

    # ── 3. 디스크 사용률 ──
    try:
        if not await _recently_alerted(session, "system", cooldown):
            disk = psutil.disk_usage("/")
            if disk.percent >= settings.alert_disk_usage_threshold:
                alerts.append({
                    "category": "system",
                    "severity": "critical" if disk.percent >= 95 else "warning",
                    "title": f"디스크 사용률 경고: {disk.percent}%",
                    "summary": f"디스크 사용률이 {disk.percent}%에 도달했습니다.\n전체: {disk.total // (1024**3)}GB / 사용: {disk.used // (1024**3)}GB / 남은 공간: {disk.free // (1024**3)}GB\n임계치: {settings.alert_disk_usage_threshold}%",
                    "details": {
                        "disk_percent": disk.percent,
                        "disk_total_gb": disk.total // (1024**3),
                        "disk_used_gb": disk.used // (1024**3),
                        "disk_free_gb": disk.free // (1024**3),
                        "threshold": settings.alert_disk_usage_threshold,
                    },
                })
    except Exception as e:
        logger.warning(f"디스크 알림 체크 실패: {e}")

    # ── 4. 메모리 사용률 ──
    try:
        if not await _recently_alerted(session, "system_memory", cooldown):
            mem = psutil.virtual_memory()
            if mem.percent >= settings.alert_memory_usage_threshold:
                alerts.append({
                    "category": "system_memory",
                    "severity": "critical" if mem.percent >= 95 else "warning",
                    "title": f"메모리 사용률 경고: {mem.percent}%",
                    "summary": f"메모리 사용률이 {mem.percent}%에 도달했습니다.\n전체: {mem.total // (1024**3)}GB / 사용: {mem.used // (1024**3)}GB",
                    "details": {
                        "memory_percent": mem.percent,
                        "memory_total_gb": mem.total // (1024**3),
                        "memory_used_gb": mem.used // (1024**3),
                    },
                })
    except Exception as e:
        logger.warning(f"메모리 알림 체크 실패: {e}")

    # ── 5. CPU 사용률 ──
    try:
        if not await _recently_alerted(session, "system_cpu", cooldown):
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent >= settings.alert_cpu_threshold:
                alerts.append({
                    "category": "system_cpu",
                    "severity": "critical" if cpu_percent >= 95 else "warning",
                    "title": f"CPU 사용률 경고: {cpu_percent}%",
                    "summary": f"CPU 사용률이 {cpu_percent}%에 도달했습니다.\n임계치: {settings.alert_cpu_threshold}%\nCPU 코어: {psutil.cpu_count()}개",
                    "details": {
                        "cpu_percent": cpu_percent,
                        "cpu_count": psutil.cpu_count(),
                        "threshold": settings.alert_cpu_threshold,
                    },
                })
    except Exception as e:
        logger.warning(f"CPU 알림 체크 실패: {e}")

    return alerts
