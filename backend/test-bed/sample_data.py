"""
Sample Korean news article data for testing News Origin analysis engine.

This module provides realistic test data for:
- Article clustering (same/derivative/related/isolated)
- Lifecycle stage detection (origin, spread, explosion, sustained, fadeout)
- Timeline generation
- Explosion point detection
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID
import math


# Base timestamp for the news event
BASE_TIME = datetime(2024, 2, 1, 9, 0, 0, tzinfo=timezone.utc)


SAMPLE_ARTICLES = [
    # ORIGIN STAGE - First article (삼성전자 반도체 투자)
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "url": "https://www.yonhapnews.co.kr/economy/2024020109000001",
        "title": "삼성전자, 평택 반도체 공장에 30조원 추가 투자 발표",
        "content": "삼성전자가 평택 반도체 공장에 30조원을 추가 투자한다고 1일 발표했다. 이번 투자로 3나노 공정 생산 능력을 대폭 확대할 예정이다. 업계에서는 글로벌 반도체 경쟁 심화에 대응하기 위한 선제적 투자로 분석하고 있다.",
        "publisher": "연합뉴스",
        "publisher_domain": "yonhapnews.co.kr",
        "published_at": BASE_TIME,
        "language": "ko"
    },

    # SPREAD STAGE - 3-6 hours later
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "url": "https://www.chosun.com/economy/2024020112000001",
        "title": "삼성, 평택에 30조 투자...반도체 패권 경쟁 본격화",
        "content": "삼성전자가 평택 반도체 단지에 30조원 규모의 대규모 투자를 단행한다. 삼성은 이번 투자를 통해 첨단 3나노 공정 라인을 증설하고 생산능력을 2배 이상 늘릴 계획이다. 반도체 업계는 미중 기술 패권 경쟁이 더욱 치열해질 것으로 전망했다.",
        "publisher": "조선일보",
        "publisher_domain": "chosun.com",
        "published_at": BASE_TIME + timedelta(hours=3),
        "language": "ko"
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "url": "https://www.joongang.co.kr/article/2024020114000001",
        "title": "[단독] 삼성전자 평택 반도체 투자 30조...일자리 5000개 창출",
        "content": "삼성전자의 평택 반도체 공장 투자로 향후 3년간 5000개 이상의 일자리가 창출될 전망이다. 삼성은 30조원을 투입해 3나노 첨단 공정 라인을 확충하고, 협력업체까지 포함하면 경제 파급효과는 100조원에 달할 것으로 예상된다.",
        "publisher": "중앙일보",
        "publisher_domain": "joongang.co.kr",
        "published_at": BASE_TIME + timedelta(hours=5),
        "language": "ko"
    },

    # EXPLOSION STAGE - 12-18 hours later (5+ articles in same hour)
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "url": "https://www.donga.com/news/economy/2024020121000001",
        "title": "삼성 30조 반도체 투자, SK하이닉스도 맞불 투자 예고",
        "content": "삼성전자의 평택 30조원 투자 발표 이후 SK하이닉스도 용인 반도체 클러스터에 대규모 투자를 검토 중인 것으로 알려졌다. 반도체 업계는 국내 양대 기업의 투자 경쟁이 글로벌 시장 점유율 확대로 이어질 것으로 기대하고 있다.",
        "publisher": "동아일보",
        "publisher_domain": "donga.com",
        "published_at": BASE_TIME + timedelta(hours=12),
        "language": "ko"
    },
    {
        "id": "55555555-5555-5555-5555-555555555555",
        "url": "https://www.hani.co.kr/arti/economy/2024020121300001",
        "title": "삼성 반도체 투자, 지역경제 활성화 vs 환경 우려 충돌",
        "content": "삼성전자의 평택 반도체 투자를 둘러싸고 지역경제 활성화 기대와 환경 우려가 맞서고 있다. 지역 상인들은 인구 유입과 소비 증가를 기대하는 반면, 환경단체들은 수질 오염과 전력 소비 급증을 우려하고 있다.",
        "publisher": "한겨레",
        "publisher_domain": "hani.co.kr",
        "published_at": BASE_TIME + timedelta(hours=12, minutes=30),
        "language": "ko"
    },
    {
        "id": "66666666-6666-6666-6666-666666666666",
        "url": "https://www.mk.co.kr/news/economy/2024020121450001",
        "title": "삼성 30조 투자 발표에 반도체 장비株 일제히 급등",
        "content": "삼성전자의 평택 반도체 투자 발표 이후 증시에서 반도체 장비 관련주가 일제히 강세를 보였다. 원익IPS, 주성엔지니어링 등 주요 장비업체 주가가 10% 이상 급등했으며, 소재·부품 업체들도 동반 상승했다.",
        "publisher": "매일경제",
        "publisher_domain": "mk.co.kr",
        "published_at": BASE_TIME + timedelta(hours=12, minutes=45),
        "language": "ko"
    },
    {
        "id": "77777777-7777-7777-7777-777777777777",
        "url": "https://www.hankyung.com/economy/article/2024020122000001",
        "title": "[속보] 정부 \"삼성 투자 적극 지원...세제 혜택 검토\"",
        "content": "정부가 삼성전자의 평택 반도체 투자에 대해 적극적인 지원 방침을 밝혔다. 산업통상자원부는 세제 혜택과 인프라 구축 지원을 검토 중이며, 반도체 특별법 제정도 추진할 계획이다.",
        "publisher": "한국경제",
        "publisher_domain": "hankyung.com",
        "published_at": BASE_TIME + timedelta(hours=13),
        "language": "ko"
    },
    {
        "id": "88888888-8888-8888-8888-888888888888",
        "url": "https://news.sbs.co.kr/news/2024020122150001",
        "title": "삼성 반도체 투자 현장 가보니...평택 일대 '들썩'",
        "content": "삼성전자의 30조원 투자 발표 이후 평택 일대가 술렁이고 있다. 현장에서 만난 주민들은 일자리 창출과 지역 발전을 기대했으며, 부동산 시장도 벌써부터 들썩이는 분위기다. 반면 교통 체증과 환경 문제를 우려하는 목소리도 나왔다.",
        "publisher": "SBS",
        "publisher_domain": "sbs.co.kr",
        "published_at": BASE_TIME + timedelta(hours=13, minutes=15),
        "language": "ko"
    },
    {
        "id": "99999999-9999-9999-9999-999999999999",
        "url": "https://news.kbs.co.kr/news/2024020122300001",
        "title": "삼성 반도체 투자에 美·中 반응은? \"韓 반도체 굴기 주목\"",
        "content": "삼성전자의 대규모 반도체 투자에 미국과 중국도 촉각을 곤두세우고 있다. 월스트리트저널은 한국의 반도체 굴기가 본격화되고 있다고 보도했으며, 중국 관영 매체들은 경계의 목소리를 냈다.",
        "publisher": "KBS",
        "publisher_domain": "kbs.co.kr",
        "published_at": BASE_TIME + timedelta(hours=13, minutes=30),
        "language": "ko"
    },

    # SUSTAINED STAGE - 24-48 hours later
    {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "url": "https://www.ytn.co.kr/news/2024020209000001",
        "title": "삼성 투자 이틀째...협력업체 \"동반성장 기대\"",
        "content": "삼성전자의 평택 투자 발표 이틀째, 협력업체들이 동반성장 기대감을 드러냈다. 반도체 소재·부품·장비 업체들은 삼성과의 장기 공급 계약 체결을 위한 논의를 시작했으며, 신규 채용도 확대할 방침이다.",
        "publisher": "YTN",
        "publisher_domain": "ytn.co.kr",
        "published_at": BASE_TIME + timedelta(hours=24),
        "language": "ko"
    },
    {
        "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "url": "https://www.edaily.co.kr/news/2024020309000001",
        "title": "[심층분석] 삼성 30조 투자, 글로벌 반도체 지형 바꿀까",
        "content": "전문가들은 삼성전자의 30조원 투자가 글로벌 반도체 공급망 재편의 전환점이 될 것으로 전망했다. 대만 TSMC와의 경쟁 구도가 더욱 치열해질 것이며, 미국의 인플레이션감축법(IRA)에 대응하는 한국 정부의 전략도 중요해졌다.",
        "publisher": "이데일리",
        "publisher_domain": "edaily.co.kr",
        "published_at": BASE_TIME + timedelta(hours=48),
        "language": "ko"
    },

    # FADEOUT STAGE - 60-72 hours later
    {
        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "url": "https://www.mt.co.kr/news/2024020421000001",
        "title": "삼성 투자 여파...평택 부동산 시장 '들썩'",
        "content": "삼성전자의 반도체 투자 발표 이후 평택 지역 부동산 시장이 요동치고 있다. 아파트 매매가는 일주일 새 5% 이상 상승했으며, 전세 수요도 급증하고 있다. 전문가들은 당분간 상승세가 이어질 것으로 전망했다.",
        "publisher": "머니투데이",
        "publisher_domain": "mt.co.kr",
        "published_at": BASE_TIME + timedelta(hours=60),
        "language": "ko"
    },
    {
        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "url": "https://www.newsis.com/view/2024020509000001",
        "title": "삼성 반도체 투자 일주일...평택시 \"인프라 확충 박차\"",
        "content": "삼성전자의 투자 발표 일주일을 맞아 평택시가 교통·주거 인프라 확충에 박차를 가하고 있다. 시는 도로 확장과 대중교통 증설을 추진하고 있으며, 주택 공급 확대 방안도 마련 중이다.",
        "publisher": "뉴시스",
        "publisher_domain": "newsis.com",
        "published_at": BASE_TIME + timedelta(hours=72),
        "language": "ko"
    },

    # ISOLATED ARTICLES (completely different topics)
    {
        "id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "url": "https://www.kyunghyang.com/sports/2024020110000001",
        "title": "손흥민, 토트넘 복귀전에서 결승골...팬들 환호",
        "content": "손흥민이 부상에서 복귀한 첫 경기에서 결승골을 터뜨렸다. 토트넘은 1일 홈에서 열린 경기에서 손흥민의 활약에 힘입어 2-1로 승리했다. 손흥민은 후반 35분 극적인 역전골을 넣으며 팬들의 환호를 받았다.",
        "publisher": "경향신문",
        "publisher_domain": "kyunghyang.com",
        "published_at": BASE_TIME + timedelta(hours=1),
        "language": "ko"
    },
    {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "url": "https://www.imaeil.com/news/2024020215000001",
        "title": "전국 미세먼지 '나쁨'...외출 자제 당부",
        "content": "2일 전국 대부분 지역의 미세먼지 농도가 '나쁨' 수준을 보이고 있다. 기상청은 중국발 스모그 유입과 국내 대기 정체로 미세먼지 농도가 높아졌다며, 외출 시 마스크 착용을 당부했다.",
        "publisher": "매일신문",
        "publisher_domain": "imaeil.com",
        "published_at": BASE_TIME + timedelta(hours=30),
        "language": "ko"
    },
    {
        "id": "10101010-1010-1010-1010-101010101010",
        "url": "https://www.hankookilbo.com/culture/2024020318000001",
        "title": "봉준호 감독 신작, 칸 영화제 초청 확정",
        "content": "봉준호 감독의 신작 영화가 올해 칸 영화제에 공식 초청됐다. 영화계는 기생충에 이은 또 다른 쾌거를 기대하고 있다. 봉 감독은 이번 작품에서 SF 장르에 도전했으며, 국내외 유명 배우들이 대거 출연한다.",
        "publisher": "한국일보",
        "publisher_domain": "hankookilbo.com",
        "published_at": BASE_TIME + timedelta(hours=54),
        "language": "ko"
    },
]


def _generate_embedding_vector(seed: int, base_vector=None, noise_level=0.0) -> list[float]:
    """
    Generate a deterministic 768-dimensional pseudo-random vector.

    Args:
        seed: Seed for deterministic generation
        base_vector: Optional base vector to add noise to
        noise_level: Amount of noise to add (0.0 to 1.0)

    Returns:
        Normalized 768-dimensional vector
    """
    if base_vector is None:
        # Generate new base vector using simple PRNG
        vector = []
        for i in range(768):
            # Simple linear congruential generator
            seed = (seed * 1103515245 + 12345) & 0x7fffffff
            value = (seed / 0x7fffffff) * 2 - 1  # Range: -1 to 1
            vector.append(value)
    else:
        # Add noise to base vector
        vector = []
        for i, base_val in enumerate(base_vector):
            seed = (seed * 1103515245 + 12345) & 0x7fffffff
            noise = ((seed / 0x7fffffff) * 2 - 1) * noise_level
            vector.append(base_val + noise)

    # Normalize the vector
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude > 0:
        vector = [v / magnitude for v in vector]

    return vector


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    return dot_product  # Already normalized, so dot product = cosine similarity


# Generate embeddings with realistic similarity patterns
_BASE_SAMSUNG_EMBEDDING = _generate_embedding_vector(seed=42)  # Samsung semiconductor topic
_BASE_SOCCER_EMBEDDING = _generate_embedding_vector(seed=12345)  # Soccer topic
_BASE_WEATHER_EMBEDDING = _generate_embedding_vector(seed=67890)  # Weather topic
_BASE_MOVIE_EMBEDDING = _generate_embedding_vector(seed=11111)  # Movie topic

SAMPLE_EMBEDDINGS = {
    # Same event - very high similarity (> 0.9)
    "11111111-1111-1111-1111-111111111111": _generate_embedding_vector(100, _BASE_SAMSUNG_EMBEDDING, 0.05),
    "22222222-2222-2222-2222-222222222222": _generate_embedding_vector(101, _BASE_SAMSUNG_EMBEDDING, 0.05),
    "33333333-3333-3333-3333-333333333333": _generate_embedding_vector(102, _BASE_SAMSUNG_EMBEDDING, 0.06),
    "44444444-4444-4444-4444-444444444444": _generate_embedding_vector(103, _BASE_SAMSUNG_EMBEDDING, 0.07),
    "55555555-5555-5555-5555-555555555555": _generate_embedding_vector(104, _BASE_SAMSUNG_EMBEDDING, 0.08),
    "66666666-6666-6666-6666-666666666666": _generate_embedding_vector(105, _BASE_SAMSUNG_EMBEDDING, 0.06),
    "77777777-7777-7777-7777-777777777777": _generate_embedding_vector(106, _BASE_SAMSUNG_EMBEDDING, 0.07),
    "88888888-8888-8888-8888-888888888888": _generate_embedding_vector(107, _BASE_SAMSUNG_EMBEDDING, 0.08),

    # Derivative articles - high similarity (0.75-0.89)
    "99999999-9999-9999-9999-999999999999": _generate_embedding_vector(200, _BASE_SAMSUNG_EMBEDDING, 0.15),

    # Related articles - medium similarity (0.60-0.74)
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa": _generate_embedding_vector(300, _BASE_SAMSUNG_EMBEDDING, 0.25),
    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb": _generate_embedding_vector(301, _BASE_SAMSUNG_EMBEDDING, 0.28),
    "cccccccc-cccc-cccc-cccc-cccccccccccc": _generate_embedding_vector(302, _BASE_SAMSUNG_EMBEDDING, 0.30),
    "dddddddd-dddd-dddd-dddd-dddddddddddd": _generate_embedding_vector(303, _BASE_SAMSUNG_EMBEDDING, 0.32),

    # Isolated articles - very different (< 0.5)
    "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee": _BASE_SOCCER_EMBEDDING,
    "ffffffff-ffff-ffff-ffff-ffffffffffff": _BASE_WEATHER_EMBEDDING,
    "10101010-1010-1010-1010-101010101010": _BASE_MOVIE_EMBEDDING,
}


SAMPLE_TIMELINE_ENTRIES = [
    {
        "timestamp": BASE_TIME,
        "stage": "origin",
        "article_count": 1,
        "representative_article": {
            "id": "11111111-1111-1111-1111-111111111111",
            "title": "삼성전자, 평택 반도체 공장에 30조원 추가 투자 발표",
            "publisher": "연합뉴스",
        }
    },
    {
        "timestamp": BASE_TIME + timedelta(hours=3),
        "stage": "spread",
        "article_count": 2,
        "representative_article": {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "삼성, 평택에 30조 투자...반도체 패권 경쟁 본격화",
            "publisher": "조선일보",
        }
    },
    {
        "timestamp": BASE_TIME + timedelta(hours=12),
        "stage": "explosion",
        "article_count": 6,
        "representative_article": {
            "id": "44444444-4444-4444-4444-444444444444",
            "title": "삼성 30조 반도체 투자, SK하이닉스도 맞불 투자 예고",
            "publisher": "동아일보",
        }
    },
    {
        "timestamp": BASE_TIME + timedelta(hours=24),
        "stage": "sustained",
        "article_count": 1,
        "representative_article": {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "title": "삼성 투자 이틀째...협력업체 \"동반성장 기대\"",
            "publisher": "YTN",
        }
    },
    {
        "timestamp": BASE_TIME + timedelta(hours=60),
        "stage": "fadeout",
        "article_count": 2,
        "representative_article": {
            "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "title": "삼성 투자 여파...평택 부동산 시장 '들썩'",
            "publisher": "머니투데이",
        }
    },
]


EXPECTED_EXPLOSION_POINTS = [
    {
        "timestamp": BASE_TIME + timedelta(hours=12),
        "hour_window": (BASE_TIME + timedelta(hours=12), BASE_TIME + timedelta(hours=13)),
        "article_count": 6,
        "articles": [
            "44444444-4444-4444-4444-444444444444",
            "55555555-5555-5555-5555-555555555555",
            "66666666-6666-6666-6666-666666666666",
            "77777777-7777-7777-7777-777777777777",
            "88888888-8888-8888-8888-888888888888",
            "99999999-9999-9999-9999-999999999999",
        ]
    }
]


def get_sample_articles() -> list[dict]:
    """
    Get the list of sample articles.

    Returns:
        List of article dictionaries
    """
    return SAMPLE_ARTICLES


def get_article_by_id(article_id: str) -> dict | None:
    """
    Get a specific article by its ID.

    Args:
        article_id: UUID string of the article

    Returns:
        Article dict if found, None otherwise
    """
    for article in SAMPLE_ARTICLES:
        if article["id"] == article_id:
            return article
    return None


def get_embedding_by_id(article_id: str) -> list[float] | None:
    """
    Get the embedding vector for a specific article.

    Args:
        article_id: UUID string of the article

    Returns:
        768-dimensional embedding vector if found, None otherwise
    """
    return SAMPLE_EMBEDDINGS.get(article_id)


def calculate_similarity(article_id1: str, article_id2: str) -> float | None:
    """
    Calculate cosine similarity between two articles.

    Args:
        article_id1: First article UUID
        article_id2: Second article UUID

    Returns:
        Cosine similarity score (0.0 to 1.0) if both embeddings found, None otherwise
    """
    emb1 = get_embedding_by_id(article_id1)
    emb2 = get_embedding_by_id(article_id2)

    if emb1 is None or emb2 is None:
        return None

    return _cosine_similarity(emb1, emb2)
