"""
# limiter.py - Rate Limiter Configuration
# Version: 0.1.0
# Description: slowapi-based rate limiting setup
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import get_settings

settings = get_settings()

# Use memory storage in test mode, Redis otherwise
storage_uri = "memory://" if settings.app_env == "test" else settings.redis_url

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
    default_limits=["60/minute"],
    enabled=settings.app_env != "test",
)
