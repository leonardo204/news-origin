"""
# category.py - Article Category Classification Service
# Version: 0.1.0
# Description: 기사 카테고리 분류 (HTML 메타 → RSS feed → 키워드 매칭)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 표준 카테고리 키
STANDARD_CATEGORIES = {"headlines", "politics", "economy", "society", "tech", "entertainment"}

# 한국어/영어 카테고리명 → 표준 키 매핑
CATEGORY_NORMALIZE_MAP: dict[str, str] = {
    # 정치
    "정치": "politics",
    "politics": "politics",
    "political": "politics",
    "국회": "politics",
    "청와대": "politics",
    # 경제
    "경제": "economy",
    "economy": "economy",
    "business": "economy",
    "finance": "economy",
    "금융": "economy",
    "증권": "economy",
    "부동산": "economy",
    "산업": "economy",
    "market": "economy",
    "money": "economy",
    # 사회
    "사회": "society",
    "society": "society",
    "national": "society",
    "지역": "society",
    "교육": "society",
    "환경": "society",
    "건강": "society",
    "의료": "society",
    "복지": "society",
    # IT/과학
    "it": "tech",
    "과학": "tech",
    "기술": "tech",
    "tech": "tech",
    "technology": "tech",
    "science": "tech",
    "digital": "tech",
    "ai": "tech",
    "모바일": "tech",
    "인터넷": "tech",
    # 연예/문화
    "연예": "entertainment",
    "문화": "entertainment",
    "entertainment": "entertainment",
    "culture": "entertainment",
    "lifestyle": "entertainment",
    "life": "entertainment",
    "스포츠": "entertainment",
    "sports": "entertainment",
    "sport": "entertainment",
    "레저": "entertainment",
    "여행": "entertainment",
    # 국제 → headlines (별도 카테고리 없으므로)
    "국제": "headlines",
    "세계": "headlines",
    "world": "headlines",
    "international": "headlines",
    "global": "headlines",
    # 헤드라인/일반
    "종합": "headlines",
    "헤드라인": "headlines",
    "headlines": "headlines",
    "general": "headlines",
    "news": "headlines",
    "opinion": "headlines",
    "오피니언": "headlines",
    "사설": "headlines",
}

# 제목 키워드 → 카테고리 매핑
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "politics": [
        "대통령", "국회", "여당", "야당", "정부", "청와대", "총리", "장관",
        "의원", "국무회의", "선거", "투표", "당대표", "비대위", "탄핵",
        "국민의힘", "더불어민주당", "민주당", "정의당", "조국혁신당",
        "외교", "통일", "북한", "남북", "한미", "국방",
    ],
    "economy": [
        "코스피", "코스닥", "주가", "금리", "환율", "물가", "GDP",
        "한국은행", "기준금리", "인플레이션", "경기", "수출", "수입",
        "무역", "투자", "부동산", "아파트", "전세", "매매",
        "증시", "주식", "채권", "펀드", "은행", "보험",
        "삼성", "현대", "SK", "LG", "포스코", "카카오", "네이버",
    ],
    "society": [
        "경찰", "검찰", "법원", "재판", "판결", "구속", "체포",
        "사고", "사건", "화재", "지진", "태풍", "폭우", "홍수",
        "교육", "학교", "대학", "수능", "입시",
        "코로나", "방역", "백신", "감염", "확진",
        "인구", "출산", "고령화", "자살", "범죄",
    ],
    "tech": [
        "AI", "인공지능", "ChatGPT", "GPT", "반도체", "칩",
        "스마트폰", "아이폰", "갤럭시", "애플", "구글", "마이크로소프트",
        "로봇", "자율주행", "전기차", "배터리", "우주", "NASA",
        "5G", "6G", "클라우드", "메타버스", "블록체인", "비트코인",
        "사이버", "해킹", "보안", "데이터", "플랫폼",
    ],
    "entertainment": [
        "드라마", "영화", "배우", "감독", "아이돌", "가수",
        "콘서트", "앨범", "음원", "차트", "방송", "예능",
        "BTS", "블랙핑크", "뉴진스", "에스파", "세븐틴",
        "넷플릭스", "디즈니", "웹툰", "게임",
        "올림픽", "월드컵", "야구", "축구", "농구",
        "프로야구", "KBO", "K리그", "EPL", "MLB",
        "손흥민", "이강인", "오타니",
    ],
}


def extract_category_from_html(html: str) -> Optional[str]:
    """
    HTML 메타 태그에서 기사 카테고리 추출

    지원 메타 태그:
    - <meta property="article:section" content="...">
    - <meta property="og:article:section" content="...">
    - <meta name="article:section" content="...">
    - <meta name="news_keywords" content="...">  (첫 번째 키워드)
    """
    # article:section 계열
    patterns = [
        r'<meta\s+(?:property|name)\s*=\s*["\'](?:og:)?article:section["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        r'<meta\s+content\s*=\s*["\']([^"\']+)["\']\s+(?:property|name)\s*=\s*["\'](?:og:)?article:section["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            normalized = normalize_category(raw)
            if normalized:
                return normalized

    # news_keywords 폴백 (첫 번째 키워드만)
    kw_match = re.search(
        r'<meta\s+(?:name|property)\s*=\s*["\']news_keywords["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if kw_match:
        first_kw = kw_match.group(1).split(",")[0].strip()
        normalized = normalize_category(first_kw)
        if normalized:
            return normalized

    return None


def normalize_category(raw: str | None) -> Optional[str]:
    """다양한 카테고리명을 표준 키로 정규화"""
    if not raw:
        return None

    lowered = raw.strip().lower()

    # 직접 매핑
    if lowered in CATEGORY_NORMALIZE_MAP:
        return CATEGORY_NORMALIZE_MAP[lowered]

    # 부분 매칭 (예: "IT/과학" → "it" 포함)
    for key, standard in CATEGORY_NORMALIZE_MAP.items():
        if key in lowered:
            return standard

    return None


def classify_by_keywords(title: str) -> Optional[str]:
    """제목 키워드 매칭으로 카테고리 분류"""
    if not title:
        return None

    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in title)
        if count > 0:
            scores[category] = count

    if not scores:
        return None

    # 가장 많이 매칭된 카테고리
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def resolve_category(
    source_category: str | None = None,
    feed_category: str | None = None,
    title: str | None = None,
) -> Optional[str]:
    """
    3단 폴백 카테고리 결정

    1순위: HTML 메타 태그에서 추출한 카테고리 (source_category)
    2순위: RSS feed 카테고리 (feed_category)
    3순위: 제목 키워드 매칭
    """
    # 1순위: 원문 카테고리
    if source_category and source_category in STANDARD_CATEGORIES:
        return source_category

    # 2순위: RSS 피드 카테고리 (headlines 제외 - 너무 범용적)
    if feed_category and feed_category in STANDARD_CATEGORIES and feed_category != "headlines":
        return feed_category

    # 3순위: 키워드 매칭
    if title:
        keyword_cat = classify_by_keywords(title)
        if keyword_cat:
            return keyword_cat

    # 최종 폴백: feed_category가 headlines이면 그대로 사용
    if feed_category and feed_category in STANDARD_CATEGORIES:
        return feed_category

    return None
