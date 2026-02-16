"""
# news_feed.py - Category News Feed Service
# Version: 0.3.0
# Description: Google News RSS + 한국 주요 언론사 RSS 피드 수집 (백그라운드 크롤링용)
# Changes:
#   - 0.1.0: 카테고리별 RSS 피드 수집, URL 중복 제거
#   - 0.2.0: 한국 주요 언론사 RSS 피드 수집 추가 (네이버 뉴스 대체)
#   - 0.3.0: RSS 피드 수집 병렬화 (asyncio.gather)
"""

import asyncio
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
        timeout=float(settings.news_search_timeout),
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
    # 카테고리별로 병렬 수집 후 라운드로빈으로 균등 분배
    category_articles: dict[str, list[dict]] = {}
    seen_urls = set()

    # asyncio.gather로 병렬 수집
    tasks = [
        fetch_category_feed(feed_url, limit=limit_per_category)
        for name, feed_url in categories.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (name, feed_url), result in zip(categories.items(), results):
        if isinstance(result, Exception):
            logger.warning(f"Feed [{name}] failed: {result}")
            continue

        try:
            articles = result
            unique = []
            for article in articles:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    article["feed_category"] = name
                    unique.append(article)
            category_articles[name] = unique
            logger.info(f"Feed [{name}]: {len(unique)} unique articles fetched")
        except Exception as e:
            logger.warning(f"Feed [{name}] processing failed: {e}")
            continue

    # 라운드로빈: 각 카테고리에서 1건씩 번갈아 선택하여 균등 분배
    result = []
    max_len = max((len(v) for v in category_articles.values()), default=0)
    for i in range(max_len):
        for name in categories:
            if name in category_articles and i < len(category_articles[name]):
                result.append(category_articles[name][i])
                if len(result) >= max_total:
                    break
        if len(result) >= max_total:
            break

    logger.info(
        f"Total unique articles: {sum(len(v) for v in category_articles.values())}, "
        f"selected: {len(result)} (round-robin across {len(category_articles)} categories)"
    )
    return result


async def fetch_publisher_feed(
    publisher_name: str,
    feed_url: str,
    limit: int = 10,
) -> list[dict]:
    """
    한국 언론사 RSS 피드 파싱

    Google News와 달리 <source> 태그가 없으므로 publisher_name을 직접 사용.
    dc:creator가 있으면 저자로 활용.

    Returns: [{url, title, publisher, published_at}, ...]
    """
    DC_NS = "http://purl.org/dc/elements/1.1/"

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.crawl_user_agent},
        timeout=float(settings.news_search_timeout),
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(feed_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch publisher feed [{publisher_name}]: {e}")
            return []

    results = []
    try:
        root = ET.fromstring(response.text)
        items = root.findall(".//item")

        for item in items[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date_str = item.findtext("pubDate", "")

            if not link or not title:
                continue

            published_at = parse_rfc2822(pub_date_str)

            results.append({
                "url": link,
                "title": title,
                "publisher": publisher_name,
                "published_at": published_at,
            })
    except ET.ParseError:
        logger.warning(f"Failed to parse publisher RSS [{publisher_name}]: {feed_url}")

    return results


async def fetch_all_publisher_feeds(
    publishers: dict[str, str],
    limit_per_publisher: int = 10,
    max_total: int = 60,
    exclude_urls: set[str] | None = None,
) -> list[dict]:
    """
    전체 언론사 RSS 피드 수집 + URL 중복 제거

    Args:
        publishers: {publisher_name: feed_url} 매핑
        limit_per_publisher: 언론사당 최대 기사 수
        max_total: 전체 최대 기사 수
        exclude_urls: 이미 수집된 URL 집합 (Google News와 중복 방지)

    Returns: [{url, title, publisher, published_at}, ...]
    """
    seen_urls = set(exclude_urls or set())
    publisher_articles: dict[str, list[dict]] = {}

    # asyncio.gather로 병렬 수집
    tasks = [
        fetch_publisher_feed(name, feed_url, limit=limit_per_publisher)
        for name, feed_url in publishers.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (name, feed_url), result in zip(publishers.items(), results):
        if isinstance(result, Exception):
            logger.warning(f"Publisher [{name}] failed: {result}")
            continue

        try:
            articles = result
            unique = []
            for article in articles:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    unique.append(article)
            publisher_articles[name] = unique
            logger.info(f"Publisher [{name}]: {len(unique)} unique articles fetched")
        except Exception as e:
            logger.warning(f"Publisher [{name}] processing failed: {e}")
            continue

    # 라운드로빈: 각 언론사에서 1건씩 번갈아 선택하여 균등 분배
    result = []
    max_len = max((len(v) for v in publisher_articles.values()), default=0)
    for i in range(max_len):
        for name in publishers:
            if name in publisher_articles and i < len(publisher_articles[name]):
                result.append(publisher_articles[name][i])
                if len(result) >= max_total:
                    break
        if len(result) >= max_total:
            break

    logger.info(
        f"Publisher feeds: {sum(len(v) for v in publisher_articles.values())} unique, "
        f"selected: {len(result)} (round-robin across {len(publisher_articles)} publishers)"
    )
    return result
