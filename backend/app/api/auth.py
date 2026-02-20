"""
# auth.py - Admin JWT Authentication
# Version: 0.1.0
# Description: JWT 토큰 생성/검증 + FastAPI 의존성
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

_ALGORITHM = "HS256"


def create_token(username: str) -> tuple[str, datetime]:
    """JWT 토큰 생성"""
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.admin_jwt_expire_hours)
    payload = {"sub": username, "exp": expires}
    token = jwt.encode(payload, settings.app_secret_key, algorithm=_ALGORITHM)
    return token, expires


def authenticate(username: str, password: str) -> bool:
    """관리자 자격 증명 확인"""
    settings = get_settings()
    return username == settings.admin_username and password == settings.admin_password


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """보호된 엔드포인트용 의존성 — 유효한 JWT 필요"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.app_secret_key,
            algorithms=[_ALGORITHM],
        )
        username: str = payload.get("sub", "")
        if not username:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
