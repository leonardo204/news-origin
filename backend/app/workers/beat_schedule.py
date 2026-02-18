"""
# beat_schedule.py - Celery Beat Schedule Configuration
# Version: 0.2.0
# Description: 주기적 백그라운드 뉴스 크롤링 스케줄
# Changes:
#   - 0.1.0: fetch_trending_news (30분), cleanup_old_articles (매일 03:00)
#   - 0.2.0: retry_failed_embeddings (15분), check_worker_memory (5분)
"""

from celery.schedules import crontab

# Google News RSS 피드 URLs (한국)
# 토픽 ID는 Google이 수시로 변경하므로, 검색 RSS를 사용
CATEGORY_FEEDS = {
    "headlines": "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
    "politics": "https://news.google.com/rss/search?q=정치&hl=ko&gl=KR&ceid=KR:ko",
    "economy": "https://news.google.com/rss/search?q=경제+금융&hl=ko&gl=KR&ceid=KR:ko",
    "society": "https://news.google.com/rss/search?q=사회&hl=ko&gl=KR&ceid=KR:ko",
    "tech": "https://news.google.com/rss/search?q=IT+과학+기술&hl=ko&gl=KR&ceid=KR:ko",
    "entertainment": "https://news.google.com/rss/search?q=연예+문화&hl=ko&gl=KR&ceid=KR:ko",
    "sports": "https://news.google.com/rss/search?q=스포츠&hl=ko&gl=KR&ceid=KR:ko",
}

# 한국 주요 언론사 RSS 피드 (네이버 뉴스 대체)
PUBLISHER_FEEDS = {
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    "한국경제": "https://www.hankyung.com/feed/all-news",
    "한겨레": "https://www.hani.co.kr/rss/",
    "경향신문": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
    "매일경제": "https://www.mk.co.kr/rss/40300001/",
    "동아일보": "https://rss.donga.com/total.xml",
}

# 배치 설정
FEED_LIMIT_PER_CATEGORY = 15  # RSS 피드 카테고리당 최대 수집 수
PUBLISHER_FEED_LIMIT = 10     # 언론사 피드당 최대 수집 수
CRAWL_BATCH_SIZE = 50         # 크롤링 배치 크기
MAX_ARTICLES_PER_RUN = 90     # 실행당 최대 기사 수 (Google News)
ARTICLE_RETENTION_DAYS = 90

# Celery Beat 스케줄
beat_schedule = {
    "fetch-trending-news-every-30min": {
        "task": "app.workers.tasks.fetch_trending_news",
        "schedule": crontab(minute="*/30"),
    },
    "cleanup-old-articles-daily": {
        "task": "app.workers.tasks.cleanup_old_articles",
        "schedule": crontab(hour=3, minute=0),  # 매일 03:00 KST
    },
    "retry-failed-embeddings-every-15min": {
        "task": "app.workers.tasks.retry_failed_embeddings",
        "schedule": crontab(minute="*/15"),
    },
    "check-worker-memory-every-5min": {
        "task": "app.workers.tasks.check_worker_memory",
        "schedule": crontab(minute="*/5"),
    },
}
