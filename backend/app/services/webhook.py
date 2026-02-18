"""
# webhook.py - Discord-compatible Webhook Notification Service
# Version: 0.2.0
# Description: 웹훅 알림 전송 (Discord embed 포맷)
# Changes:
#   - 0.1.0: Initial async implementation
#   - 0.2.0: Sync implementation for Celery task use, fire-and-forget
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def send_webhook(
    title: str,
    description: str,
    color: int = 0x3498DB,
    fields: list[dict] | None = None,
) -> None:
    """
    Discord-compatible 웹훅 알림 전송 (동기, fire-and-forget)

    webhook_url이 비어있으면 조용히 건너뜀.
    실패 시 로깅만 하고 예외를 전파하지 않음 (메인 태스크에 영향 없음).

    Args:
        title: 임베드 제목
        description: 임베드 설명
        color: 임베드 색상 (기본: Discord 파란색)
        fields: Discord embed fields 리스트 [{"name": ..., "value": ..., "inline": bool}]
    """
    from app.config import get_settings
    import httpx

    settings = get_settings()
    if not settings.webhook_url:
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields or [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    try:
        response = httpx.post(settings.webhook_url, json=payload, timeout=5.0)
        response.raise_for_status()
        logger.info(f"Webhook sent: {title}")
    except Exception as e:
        logger.warning(f"Webhook notification failed: {e}")
