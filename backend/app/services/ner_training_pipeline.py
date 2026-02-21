"""
# ner_training_pipeline.py - NER Training Data Pipeline
# Version: 0.1.0
# Description: GPT 평가 결과 → BIO 태그 변환 → DB 영속화 파이프라인
# Changes:
#   - 0.1.0: BIO 태그 변환, 학습 데이터 저장, 배치 평가 결과 저장
"""

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


def convert_to_bio_tags(title: str, entities: list[dict]) -> list[tuple[str, str]]:
    """
    GPT corrected_entities → BIO 태그 시퀀스 변환

    "윤석열 대통령이 방미" + [{text:"윤석열", type:"PS", start_char:0, end_char:3}]
    → [("윤","B-PS"), ("석","I-PS"), ("열","I-PS"), (" ","O"), ("대","O"), ...]

    Args:
        title: 기사 제목 원문
        entities: GPT가 교정한 엔터티 목록 [{text, type, start_char, end_char}]

    Returns:
        문자 단위 BIO 태그 시퀀스 [(char, tag), ...]
    """
    # 기본: 모든 문자를 O 태그로 초기화
    tags = ["O"] * len(title)

    # 엔터티 위치를 start_char 기준으로 정렬 (겹침 방지)
    sorted_entities = sorted(entities, key=lambda e: e.get("start_char", 0))

    for entity in sorted_entities:
        text = entity.get("text", "")
        etype = entity.get("type", "O")
        start = entity.get("start_char")
        end = entity.get("end_char")

        if start is None or end is None:
            # start/end가 없으면 제목에서 위치 탐색
            idx = title.find(text)
            if idx == -1:
                continue
            start = idx
            end = idx + len(text)

        # 범위 검증
        if start < 0 or end > len(title) or start >= end:
            continue

        # 제목에서 실제 텍스트와 일치하는지 확인
        actual = title[start:end]
        if actual != text:
            # 불일치 시 위치 재탐색
            idx = title.find(text)
            if idx == -1:
                continue
            start = idx
            end = idx + len(text)

        # BIO 태그 할당
        for i in range(start, end):
            if i >= len(tags):
                break
            if i == start:
                tags[i] = f"B-{etype}"
            else:
                tags[i] = f"I-{etype}"

    return list(zip(title, tags))


def save_training_sample(
    session_factory,
    article_id: Optional[str],
    title: str,
    bio_tags: list[tuple[str, str]],
    gpt_quality_score: float,
    gpt_corrected_entities: list[dict],
    original_entities: list[dict] | None = None,
    gpt_reasoning: str = "",
    model_version: str = "",
    extraction_method: str = "unknown",
) -> Optional[str]:
    """
    ner_training_samples 테이블에 학습 데이터 저장 (동기)

    Returns:
        저장된 샘플 ID (실패 시 None)
    """
    import asyncio

    async def _save():
        from app.models.ner_training import NerTrainingSample

        sample = NerTrainingSample(
            article_id=uuid.UUID(article_id) if article_id else None,
            title=title,
            bio_tags=[list(pair) for pair in bio_tags],
            gpt_quality_score=gpt_quality_score,
            gpt_corrected_entities=gpt_corrected_entities,
            original_entities=original_entities or [],
            gpt_reasoning=gpt_reasoning,
            extraction_model_version=model_version,
            extraction_method=extraction_method,
        )

        async with session_factory() as db:
            db.add(sample)
            await db.commit()
            return str(sample.id)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_save())
    except Exception as e:
        logger.error(f"Failed to save training sample: {e}")
        return None
    finally:
        loop.close()


async def save_evaluation_results(
    eval_results: list[dict],
    model_version: str,
    session_factory=None,
) -> int:
    """
    evaluate_batch_sample 결과를 일괄 DB 저장 (async)

    evaluate_batch_sample에서 이미 GPT-5 평가를 수행했으므로
    결과를 직접 재사용하여 DB에 저장.

    Args:
        eval_results: evaluate_batch_sample 반환값
            [{"title": "...", "keywords_data": {...}, "evaluation": {...}}, ...]
        model_version: 현재 BERT NER 모델 버전
        session_factory: DB async 세션 팩토리

    Returns:
        저장된 샘플 수
    """
    from app.models.ner_training import NerTrainingSample

    saved_count = 0

    for result in eval_results:
        try:
            title = result.get("title", "")
            keywords_data = result.get("keywords_data", {})
            evaluation = result.get("evaluation", {})
            score = evaluation.get("score", -1)

            # 평가 실패한 경우만 스킵 (score < 0 = GPT 호출 자체가 실패)
            if score < 0:
                continue

            # evaluate_batch_sample에서 이미 evaluate_and_correct()를 호출했으므로
            # 결과를 직접 재사용 (이중 GPT-5 호출 방지)
            corrected_entities = evaluation.get("corrected_entities", [])
            if not corrected_entities:
                continue

            reasoning = evaluation.get("feedback", "")

            # BIO 태그 변환
            bio_tags = convert_to_bio_tags(title, corrected_entities)

            # DB 저장 (async - Celery async task 내에서 호출)
            sample = NerTrainingSample(
                article_id=None,
                title=title,
                bio_tags=[list(pair) for pair in bio_tags],
                gpt_quality_score=score,
                gpt_corrected_entities=corrected_entities,
                original_entities=keywords_data.get("entities", []),
                gpt_reasoning=reasoning,
                extraction_model_version=model_version,
                extraction_method=keywords_data.get("method", "unknown"),
            )

            try:
                async with session_factory() as db:
                    db.add(sample)
                    await db.commit()
                    saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save training sample: {e}")

        except Exception as e:
            logger.warning(f"Failed to process eval result for '{result.get('title', '')[:50]}': {e}")
            continue

    logger.info(f"Saved {saved_count}/{len(eval_results)} evaluation results as training samples")
    return saved_count
