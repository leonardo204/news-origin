"""
# news_search.py - News Search Service
# Version: 0.1.0
# Description: Google News RSS + GNews API 기반 뉴스 검색
# Changes:
#   - 0.1.0: Google News RSS 검색, GNews API 폴백
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

import httpx

from app.config import get_settings

settings = get_settings()


async def search_news(query: str, limit: int = 10) -> list[dict]:
    """
    뉴스 검색 (Google News RSS 우선, GNews 폴백)

    [BUSINESS LOGIC - DO NOT MODIFY]
    Google News RSS → GNews API 순서로 검색
    Google News RSS가 무료/무제한이므로 우선 사용
    """
    results = await _search_google_news_rss(query, limit)

    # Google News 결과가 부족하면 GNews 보조
    if len(results) < limit and settings.gnews_api_key:
        gnews_results = await _search_gnews(query, limit - len(results))
        results.extend(gnews_results)

    return results[:limit]


async def _search_google_news_rss(query: str, limit: int = 10) -> list[dict]:
    """
    Google News RSS 검색

    [CRITICAL] 무료 + 무제한이므로 항상 첫 번째로 시도
    """
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.crawl_user_agent},
        timeout=15.0,
    ) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

    results = []
    try:
        root = ET.fromstring(response.text)
        items = root.findall(".//item")

        for item in items[:limit]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date_str = item.findtext("pubDate", "")
            source = item.findtext("source", "")

            # 발행 시간 파싱 (RFC 2822)
            published_at = _parse_rfc2822(pub_date_str)

            if link:
                results.append({
                    "url": link,
                    "title": _clean_title(title, source),
                    "publisher": source,
                    "published_at": published_at,
                })
    except ET.ParseError:
        pass

    return results


async def _search_gnews(query: str, limit: int = 10) -> list[dict]:
    """GNews API 검색 (보조)"""
    if not settings.gnews_api_key:
        return []

    url = "https://gnews.io/api/v4/search"
    params = {
        "q": query,
        "lang": "ko",
        "country": "kr",
        "max": min(limit, 10),
        "apikey": settings.gnews_api_key,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return []

    return [
        {
            "url": article.get("url", ""),
            "title": article.get("title", ""),
            "publisher": article.get("source", {}).get("name", ""),
            "published_at": _parse_iso(article.get("publishedAt")),
        }
        for article in data.get("articles", [])
    ]


def _parse_rfc2822(date_str: str) -> Optional[datetime]:
    """RFC 2822 날짜 파싱"""
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


def _parse_iso(date_str: Optional[str]) -> Optional[datetime]:
    """ISO 8601 날짜 파싱"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean_title(title: str, source: str) -> str:
    """Google News RSS 제목에서 소스명 제거"""
    # "기사 제목 - 언론사명" 패턴에서 언론사명 제거
    if source and title.endswith(f" - {source}"):
        return title[: -(len(source) + 3)]
    return title
