"""
# crawler.py - News Article Crawler Engine
# Version: 0.1.0
# Description: trafilatura/newspaper4k 기반 뉴스 기사 크롤링 및 메타데이터 추출
# Changes:
#   - 0.1.0: Initial implementation with trafilatura + newspaper4k fallback
"""

import asyncio
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from typing import Optional

settings = get_settings()


async def crawl_article(url: str) -> Optional[dict]:
    """
    URL에서 기사 크롤링

    [CRITICAL] trafilatura 우선, 실패 시 newspaper4k 폴백
    이 순서를 변경하면 정확도가 크게 저하됨

    [BUSINESS LOGIC - DO NOT MODIFY]
    크롤링 간격은 최소 crawl_delay_seconds(기본 2초)를 유지해야 함 (robots.txt 준수)
    """
    html = await _fetch_html(url)
    if not html:
        return None

    # 1차: trafilatura (정확도 최고)
    result = _extract_with_trafilatura(html, url)

    # 2차: newspaper4k (폴백)
    if not result:
        result = await _extract_with_newspaper(url)

    if result:
        result["url"] = url
        result["publisher_domain"] = urlparse(url).netloc

    return result


async def crawl_articles_batch(urls: list[str]) -> list[dict]:
    """
    복수 URL 배치 크롤링

    [BUSINESS LOGIC]
    동시 크롤링 수를 crawl_max_concurrent로 제한
    각 요청 간 crawl_delay_seconds 지연 적용
    """
    semaphore = asyncio.Semaphore(settings.crawl_max_concurrent)
    results = []

    async def _crawl_with_limit(u: str) -> Optional[dict]:
        async with semaphore:
            result = await crawl_article(u)
            await asyncio.sleep(settings.crawl_delay_seconds)
            return result

    tasks = [_crawl_with_limit(u) for u in urls]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in raw_results:
        if isinstance(r, dict):
            results.append(r)

    return results


async def _fetch_html(url: str) -> Optional[str]:
    """HTML 다운로드"""
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.crawl_user_agent},
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError:
            return None


def _extract_with_trafilatura(html: str, url: str) -> Optional[dict]:
    """trafilatura로 기사 추출 (벤치마크 최고 정확도 F1 0.883)"""
    try:
        import trafilatura

        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            output_format="json",
            with_metadata=True,
        )

        if not result:
            return None

        import json
        data = json.loads(result)

        return {
            "title": data.get("title", ""),
            "content": data.get("text", ""),
            "author": data.get("author"),
            "publisher": data.get("sitename"),
            "published_at": _parse_date(data.get("date")),
            "summary": (data.get("text", "")[:200] + "...") if data.get("text") else None,
            "language": data.get("language", "ko"),
        }
    except Exception:
        return None


async def _extract_with_newspaper(url: str) -> Optional[dict]:
    """newspaper4k 폴백 추출"""
    try:
        from newspaper import Article as NewsArticle

        article = NewsArticle(url)
        # newspaper4k는 동기이므로 executor에서 실행
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, article.download)
        await loop.run_in_executor(None, article.parse)

        return {
            "title": article.title,
            "content": article.text,
            "author": ", ".join(article.authors) if article.authors else None,
            "publisher": urlparse(url).netloc.replace("www.", ""),
            "published_at": article.publish_date,
            "summary": article.text[:200] + "..." if article.text else None,
        }
    except Exception:
        return None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """날짜 문자열 파싱 (다양한 포맷 대응)"""
    if not date_str:
        return None
    try:
        # ISO format
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass
    try:
        # YYYY-MM-DD
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
