"""
# search.py - Search API Routes
# Version: 0.2.0
# Description: 뉴스 검색 API
"""

import logging

from fastapi import APIRouter, Query, HTTPException, Request

from app.core.limiter import limiter
from app.schemas.article import ArticleBase

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/news",
    summary="뉴스 검색",
    description="Google News RSS와 GNews API를 사용하여 뉴스 기사를 검색합니다.",
    responses={
        502: {"description": "뉴스 검색 서비스에 연결할 수 없음"},
        422: {"description": "잘못된 요청 파라미터"},
    },
)
@limiter.limit("20/minute")
async def search_news_articles(
    request: Request,
    q: str = Query(..., min_length=2, max_length=500, description="검색어"),
    limit: int = Query(10, ge=1, le=50, description="결과 수"),
) -> list[ArticleBase]:
    """뉴스 기사 검색 (Google News RSS + GNews)"""
    from app.services.news_search import search_news

    logger.info(f"News search: q={q[:80]!r}, limit={limit}")
    try:
        results = await search_news(q, limit=limit)
    except Exception as e:
        logger.error(f"News search failed: {e}")
        raise HTTPException(status_code=502, detail="뉴스 검색 서비스에 연결할 수 없습니다.")

    return [ArticleBase(**r) for r in results]
