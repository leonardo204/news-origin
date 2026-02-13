"""
# news_feed.py - Category News Feed Service
# Version: 0.1.0
# Description: Google News RSS 카테고리 피드 수집 (백그라운드 크롤링용)
# Changes:
#   - 0.1.0: 카테고리별 RSS 피드 수집, URL 중복 제거
"""

import logging
import xml.etree.ElementTree as ET

import httpx

from app.config import get_settings
from app.services.news_search import decode_google_news_url, parse_rfc2822, clean_title

settings = get_settings()
logger = logging.getLogger(__name__)


async def fetch_category_feed(feed_url: str, limit: int = 20) -> list[dict]:
    """
    단일 Google News RSS 카테고리 피드 파싱

    Returns: [{url, title, publisher, published_at}, ...]
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.crawl_user_agent},
        timeout=15.0,
    ) as client:
        try:
            response = await client.get(feed_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch feed {feed_url}: {e}")
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

            published_at = parse_rfc2822(pub_date_str)

            if not link:
                continue

            # Google News redirect URL -> actual article URL
            # 디코딩 실패해도 Google News URL을 그대로 유지 (크롤러가 해결)
            actual_url = link
            if "news.google.com" in link:
                decoded = decode_google_news_url(link)
                if decoded:
                    actual_url = decoded
                else:
                    logger.debug(f"Google News URL decode failed, keeping original: {link[:80]}")

            results.append({
                "url": actual_url,
                "title": clean_title(title, source),
                "publisher": source,
                "published_at": published_at,
            })
    except ET.ParseError:
        logger.warning(f"Failed to parse RSS feed: {feed_url}")

    return results


async def fetch_all_category_feeds(
    categories: dict[str, str],
    limit_per_category: int = 15,
    max_total: int = 50,
) -> list[dict]:
    """
    전체 카테고리 RSS 피드 수집 + URL 중복 제거

    Args:
        categories: {name: feed_url} 매핑
        limit_per_category: 카테고리당 최대 기사 수
        max_total: 전체 최대 기사 수

    Returns: [{url, title, publisher, published_at}, ...]
    """
    all_articles = []
    seen_urls = set()

    for name, feed_url in categories.items():
        try:
            articles = await fetch_category_feed(feed_url, limit=limit_per_category)
            for article in articles:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    article["feed_category"] = name
                    all_articles.append(article)
            logger.info(f"Feed [{name}]: {len(articles)} articles fetched")
        except Exception as e:
            logger.warning(f"Feed [{name}] failed: {e}")
            continue

    logger.info(f"Total unique articles from feeds: {len(all_articles)}")
    return all_articles[:max_total]
