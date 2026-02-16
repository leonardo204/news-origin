"""
# evaluator.py - GPT-5o-mini 품질 평가 서비스
# Version: 0.1.0
# Description: Azure OpenAI GPT-5o-mini 기반 NER/클러스터 품질 평가
# Changes:
#   - 0.1.0: NER 키워드 평가, 클러스터 품질 평가, 샘플링 전략
"""

import json
import logging
import random
from typing import Optional

from app.services.azure_openai import call_gpt_sync

logger = logging.getLogger(__name__)


def evaluate_keywords(
    title: str,
    keywords_data: dict,
    max_retries: int = 2,
) -> dict:
    """
    NER 키워드 추출 품질 평가 (GPT-5o-mini)

    Args:
        title: 기사 제목
        keywords_data: 추출된 키워드 데이터

    Returns:
        {"score": 0.0~1.0, "feedback": "...", "suggested_keywords": [...]}
    """
    keywords = keywords_data.get("keywords", [])
    entities = keywords_data.get("entities", [])
    method = keywords_data.get("method", "unknown")

    entities_str = ", ".join(
        f'{e["text"]}({e["type"]})' for e in entities
    ) if entities else "없음"

    prompt = f"""다음 한국 뉴스 기사 제목에서 추출된 키워드/엔터티의 품질을 평가해주세요.

제목: {title}
추출 방법: {method}
추출된 키워드: {', '.join(keywords) if keywords else '없음'}
추출된 엔터티: {entities_str}

다음 기준으로 0.0~1.0 점수를 매기세요:
- 핵심 인물/기관/이벤트가 올바르게 추출되었는가?
- 누락된 중요 엔터티가 있는가?
- 잘못 추출된 엔터티가 있는가?

JSON 형식으로만 응답:
{{"score": 0.8, "feedback": "평가 내용", "suggested_keywords": ["올바른", "키워드"]}}"""

    for attempt in range(max_retries):
        try:
            response = call_gpt_sync(prompt)
            # JSON 파싱 (```json ... ``` 래핑 처리)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                continue  # GPT가 잘못된 JSON 반환 → 재시도
            return {"score": -1, "feedback": "GPT returned invalid JSON", "suggested_keywords": []}
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"Keyword evaluation failed after {max_retries} retries: {e}")
                return {"score": -1, "feedback": f"evaluation failed: {str(e)[:100]}", "suggested_keywords": []}


def evaluate_cluster(
    cluster_title: str,
    article_titles: list[str],
    similarity_scores: list[float],
    max_retries: int = 2,
) -> dict:
    """
    클러스터 품질 평가 (GPT-5o-mini)

    같은 클러스터에 속한 기사들이 실제로 같은 토픽인지 평가

    Returns:
        {"score": 0.0~1.0, "feedback": "...", "outliers": [...]}
    """
    articles_str = "\n".join(
        f"  {i+1}. {title} (유사도: {score:.2f})"
        for i, (title, score) in enumerate(zip(article_titles, similarity_scores))
    )

    prompt = f"""다음 뉴스 기사 클러스터의 품질을 평가해주세요.

대표 기사: {cluster_title}
클러스터 기사들:
{articles_str}

다음 기준으로 0.0~1.0 점수를 매기세요:
- 모든 기사가 실제로 같은 사건/토픽을 다루는가?
- 관련 없는 기사(outlier)가 포함되어 있는가?
- 클러스터의 일관성은 어떤가?

JSON 형식으로만 응답:
{{"score": 0.8, "feedback": "평가 내용", "outliers": [2, 5]}}"""

    for attempt in range(max_retries):
        try:
            response = call_gpt_sync(prompt)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                continue  # GPT가 잘못된 JSON 반환 → 재시도
            return {"score": -1, "feedback": "GPT returned invalid JSON", "outliers": []}
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"Cluster evaluation failed after {max_retries} retries: {e}")
                return {"score": -1, "feedback": f"evaluation failed: {str(e)[:100]}", "outliers": []}


def evaluate_batch_sample(
    articles: list[dict],
    sample_size: int = 5,
) -> list[dict]:
    """
    배치에서 샘플링하여 NER 키워드 품질 평가

    [BUSINESS LOGIC]
    매 크롤링 배치에서 sample_size건만 랜덤 샘플링하여 평가
    비용 절감 + MLOps 데이터 수집

    Args:
        articles: [{"title": "...", "keywords_data": {...}}, ...]
        sample_size: 샘플 크기

    Returns:
        [{"title": "...", "evaluation": {...}}, ...]
    """
    if not articles:
        return []

    sample = random.sample(articles, min(sample_size, len(articles)))
    results = []

    for article in sample:
        evaluation = evaluate_keywords(
            title=article["title"],
            keywords_data=article.get("keywords_data", {}),
        )
        results.append({
            "title": article["title"],
            "keywords_data": article.get("keywords_data", {}),
            "evaluation": evaluation,
        })

    # 평균 점수 로깅
    valid_scores = [r["evaluation"]["score"] for r in results if r["evaluation"]["score"] >= 0]
    if valid_scores:
        avg_score = sum(valid_scores) / len(valid_scores)
        logger.info(
            f"Keyword evaluation sample: {len(results)} articles, "
            f"avg score: {avg_score:.2f}"
        )

    return results
