"""
# deps.py - FastAPI Dependency Injection
# Version: 0.1.0
# Description: DB 세션, 설정 등 공통 의존성
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.base import get_db


async def get_session() -> AsyncSession:
    """DB 세션 의존성"""
    async for session in get_db():
        yield session


def get_config() -> Settings:
    """설정 의존성"""
    return get_settings()
