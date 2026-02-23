"""
# mlops_insight.py - MLOps Deployment Insight Generator
# Version: 0.1.1
# Description: 모델 배포 시 GPT-5로 품질 분석 인사이트 생성
# Changes:
#   - 0.1.1: GPT 빈 응답 시 최대 2회 재시도
#   - 0.1.0: generate_deployment_insight 구현
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.ner_training import NerModelVersion, NerTrainingSample

logger = logging.getLogger(__name__)


def generate_deployment_insight(
    version: str,
    new_f1: float,
    prev_f1: float | None,
    train_count: int,
) -> str | None:
    """
    모델 배포 시점에 축적된 데이터를 분석하여 GPT-5 인사이트 생성 후 DB 저장.

    Returns:
        생성된 인사이트 텍스트 또는 None (실패 시)
    """
    import asyncio

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _collect_and_generate():
        try:
            context = await _collect_context(factory, version)
            insight = _call_gpt_for_insight(
                version=version,
                new_f1=new_f1,
                prev_f1=prev_f1,
                train_count=train_count,
                context=context,
            )
            if insight:
                await _save_insight(factory, version, insight)
            return insight
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect_and_generate())
    finally:
        loop.close()


async def _collect_context(
    factory: async_sessionmaker,
    version: str,
) -> dict:
    """인사이트 생성에 필요한 데이터 수집"""
    context: dict = {
        "daily_scores": [],
        "entity_errors": {},
        "method_ratio": {"bert_ner": 0, "kiwipiepy": 0},
        "model_history": [],
        "recent_reasoning": [],
    }

    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

    async with factory() as db:
        # 1. 일별 평균 품질 (30일)
        rows = await db.execute(
            select(
                cast(NerTrainingSample.created_at, Date).label("date"),
                func.avg(NerTrainingSample.gpt_quality_score).label("avg_score"),
                func.count(NerTrainingSample.id).label("count"),
            )
            .where(NerTrainingSample.created_at >= cutoff_30d)
            .group_by(cast(NerTrainingSample.created_at, Date))
            .order_by(cast(NerTrainingSample.created_at, Date))
        )
        context["daily_scores"] = [
            {"date": str(r.date), "avg_score": round(float(r.avg_score), 3), "count": r.count}
            for r in rows.all()
        ]

        # 2. 엔터티 유형별 교정 빈도
        rows = await db.execute(
            select(NerTrainingSample.gpt_corrected_entities)
            .where(NerTrainingSample.created_at >= cutoff_30d)
        )
        type_counts: dict[str, int] = {}
        for (entities,) in rows.all():
            if isinstance(entities, list):
                for ent in entities:
                    etype = ent.get("type", "UNK") if isinstance(ent, dict) else "UNK"
                    type_counts[etype] = type_counts.get(etype, 0) + 1
        context["entity_errors"] = type_counts

        # 3. 추출 방식 비율
        rows = await db.execute(
            select(
                NerTrainingSample.extraction_method,
                func.count(NerTrainingSample.id).label("count"),
            )
            .where(NerTrainingSample.created_at >= cutoff_30d)
            .group_by(NerTrainingSample.extraction_method)
        )
        for r in rows.all():
            method = r.extraction_method or "unknown"
            if method in context["method_ratio"]:
                context["method_ratio"][method] = r.count

        # 4. 모델 버전 히스토리
        rows = await db.execute(
            select(NerModelVersion).order_by(NerModelVersion.created_at.desc()).limit(10)
        )
        context["model_history"] = [
            {
                "version": m.version,
                "f1": m.eval_f1_score,
                "precision": m.eval_precision,
                "recall": m.eval_recall,
                "samples": m.training_samples_count,
                "status": m.status,
            }
            for m in rows.scalars().all()
        ]

        # 5. 최근 평가 사유 샘플 (10건)
        rows = await db.execute(
            select(NerTrainingSample.gpt_reasoning)
            .where(NerTrainingSample.gpt_reasoning.isnot(None))
            .order_by(NerTrainingSample.created_at.desc())
            .limit(10)
        )
        context["recent_reasoning"] = [r[0] for r in rows.all() if r[0]]

    return context


def _call_gpt_for_insight(
    version: str,
    new_f1: float,
    prev_f1: float | None,
    train_count: int,
    context: dict,
) -> str | None:
    """GPT-5를 호출하여 배포 인사이트 텍스트 생성"""
    from app.services.azure_openai import call_gpt_sync

    # 프롬프트 구성
    daily_summary = "\n".join(
        f"  {d['date']}: 평균 {d['avg_score']:.3f} ({d['count']}건)"
        for d in context["daily_scores"][-14:]  # 최근 14일만
    ) or "  데이터 없음"

    entity_summary = "\n".join(
        f"  {etype}: {count}건"
        for etype, count in sorted(context["entity_errors"].items(), key=lambda x: -x[1])
    ) or "  데이터 없음"

    model_summary = "\n".join(
        f"  {m['version']}: F1={m['f1']:.4f}, P={m['precision']:.4f}, R={m['recall']:.4f} ({m['samples']}건, {m['status']})"
        for m in context["model_history"]
        if m["f1"] is not None
    ) or "  이전 모델 없음"

    method = context["method_ratio"]
    method_summary = f"  BERT NER: {method['bert_ner']}건, kiwipiepy: {method['kiwipiepy']}건"

    reasoning_summary = "\n".join(
        f"  - {r[:150]}" for r in context["recent_reasoning"][:5]
    ) or "  사유 없음"

    prompt = f"""당신은 NER MLOps 파이프라인 분석 전문가입니다.
다음 데이터를 바탕으로 모델 배포 인사이트를 생성하세요.

## 배포 정보
- 배포 버전: {version}
- 새 모델 F1: {new_f1:.4f}
- 이전 모델 F1: {f'{prev_f1:.4f}' if prev_f1 is not None else 'N/A (첫 모델)'}
- 학습 데이터: {train_count}건

## 최근 14일 일별 품질 추이
{daily_summary}

## 엔터티 유형별 교정 빈도 (30일)
{entity_summary}

## 추출 방식 비율 (30일)
{method_summary}

## 모델 버전 히스토리
{model_summary}

## 최근 GPT 평가 사유 샘플
{reasoning_summary}

다음 항목을 포함한 간결한 인사이트를 한국어로 작성하세요 (500자 이내):
1. 현재 모델 상태 요약 (1문장)
2. 이전 대비 개선/변화 포인트
3. 품질 점수 트렌드 해석
4. 주요 약점 (가장 오류가 많은 엔터티 유형)
5. 다음 사이클에서 기대되는 개선 항목
6. 데이터 간 연관 관계 (품질 추이 ↔ 모델 성능 ↔ 오류 패턴)"""

    for attempt in range(2):
        try:
            result = call_gpt_sync(
                prompt=prompt,
                system_message="당신은 NER MLOps 파이프라인 품질 분석 전문가입니다. 간결하고 실용적인 인사이트를 생성합니다.",
                max_tokens=2048,
            )
            if result and result.strip():
                logger.info(f"GPT 배포 인사이트 생성 완료 (시도 {attempt + 1}, {len(result)}자)")
                return result
            logger.warning(f"GPT 배포 인사이트 빈 응답 (시도 {attempt + 1})")
        except Exception as e:
            logger.warning(f"GPT insight generation failed (attempt {attempt + 1}): {e}")

    logger.error("GPT 배포 인사이트 생성 실패 (2회 재시도 후)")
    return None


async def _save_insight(factory: async_sessionmaker, version: str, insight: str) -> None:
    """생성된 인사이트를 NerModelVersion 레코드에 저장"""
    from sqlalchemy import update

    async with factory() as db:
        await db.execute(
            update(NerModelVersion)
            .where(NerModelVersion.version == version)
            .values(deployment_insight=insight)
        )
        await db.commit()
    logger.info(f"Deployment insight saved for {version}")
