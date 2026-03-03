"""
# report_generator.py - Admin Report Generator
# Version: 0.3.0
# Description: 정기(주간/월간) + 비정기(알림) + MLOps Fine-tuning 리포트 콘텐츠 생성
# Changes:
#   - 0.3.0: generate_finetune_report() — Fine-tuning 완료 리포트 생성 + 이메일 발송
#   - 0.2.0: 기간 비교, 일별 추이, GPT-5 내러티브, 한국어 카테고리, 상세 시스템/알림 정보
#   - 0.1.0: 초기 구현
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, cast, Date, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_report import AdminReport
from app.models.article import Article
from app.models.ner_training import NerModelVersion, NerTrainingSample
from app.models.request_log import RequestLog

logger = logging.getLogger(__name__)

CATEGORY_KR = {
    "headlines": "주요뉴스",
    "politics": "정치",
    "economy": "경제",
    "society": "사회",
    "tech": "IT/과학",
    "entertainment": "연예",
    "sports": "스포츠",
}


async def generate_periodic_report(
    session: AsyncSession,
    report_type: str,  # "weekly" or "monthly"
) -> AdminReport:
    """정기 리포트 생성 (주간/월간) — 비교 데이터 + GPT-5 내러티브 포함"""

    now = datetime.now(timezone.utc)
    if report_type == "weekly":
        period_days = 7
        period_label = "주간"
    else:
        period_days = 30
        period_label = "월간"

    period_start = now - timedelta(days=period_days)
    prev_start = period_start - timedelta(days=period_days)
    prev_end = period_start

    content: dict = {}
    summary_parts: list[str] = []
    _traffic_errors = 0  # errors section에서 참조용

    # ── 1. 크롤링 통계 ──
    try:
        article_count = (await session.execute(
            select(func.count(Article.id)).where(Article.created_at >= period_start)
        )).scalar() or 0

        prev_article_count = (await session.execute(
            select(func.count(Article.id)).where(
                Article.created_at >= prev_start,
                Article.created_at < prev_end,
            )
        )).scalar() or 0

        # 카테고리별 분포 (한국어 레이블)
        cat_col = Article.metadata_["category"].astext
        cat_rows = (await session.execute(
            select(cat_col.label("cat"), func.count().label("cnt"))
            .where(Article.created_at >= period_start, cat_col.isnot(None))
            .group_by(literal_column("cat"))
            .order_by(text("cnt DESC"))
        )).all()
        category_dist = [
            {"category": CATEGORY_KR.get(cat, cat), "key": cat, "count": cnt}
            for cat, cnt in cat_rows
        ]

        # 일별 수집량
        daily_articles = (await session.execute(
            select(
                cast(Article.created_at, Date).label("date"),
                func.count().label("cnt"),
            )
            .where(Article.created_at >= period_start)
            .group_by(cast(Article.created_at, Date))
            .order_by(cast(Article.created_at, Date))
        )).all()

        # 상위 언론사
        publisher_top = (await session.execute(
            select(Article.publisher, func.count().label("cnt"))
            .where(Article.created_at >= period_start, Article.publisher.isnot(None))
            .group_by(Article.publisher)
            .order_by(text("cnt DESC"))
            .limit(10)
        )).all()

        change_rate = round((article_count - prev_article_count) / prev_article_count * 100, 1) if prev_article_count > 0 else None

        content["crawling"] = {
            "total_articles": article_count,
            "prev_total_articles": prev_article_count,
            "change_rate": change_rate,
            "daily_breakdown": [{"date": str(d), "count": c} for d, c in daily_articles],
            "category_distribution": category_dist,
            "top_publishers": [{"name": p, "count": c} for p, c in publisher_top],
        }

        change_str = ""
        if change_rate is not None:
            change_str = f" (전기 대비 {'+'if change_rate >= 0 else ''}{change_rate}%)"
        summary_parts.append(f"수집 기사: {article_count:,}건{change_str}")
    except Exception as e:
        logger.warning(f"크롤링 통계 수집 실패: {e}")
        content["crawling"] = {"error": str(e)[:200]}
        await session.rollback()

    # ── 2. 트래픽 통계 ──
    try:
        traffic_total = (await session.execute(
            select(func.count(RequestLog.id)).where(RequestLog.created_at >= period_start)
        )).scalar() or 0

        prev_traffic = (await session.execute(
            select(func.count(RequestLog.id)).where(
                RequestLog.created_at >= prev_start,
                RequestLog.created_at < prev_end,
            )
        )).scalar() or 0

        traffic_errors = (await session.execute(
            select(func.count(RequestLog.id)).where(
                RequestLog.created_at >= period_start,
                RequestLog.status_code >= 400,
            )
        )).scalar() or 0
        _traffic_errors = traffic_errors

        avg_duration = (await session.execute(
            select(func.avg(RequestLog.duration_ms)).where(
                RequestLog.created_at >= period_start
            )
        )).scalar()

        unique_ips = (await session.execute(
            select(func.count(func.distinct(RequestLog.client_ip))).where(
                RequestLog.created_at >= period_start
            )
        )).scalar() or 0

        error_rate = round(traffic_errors / traffic_total * 100, 1) if traffic_total > 0 else 0

        # 일별 트래픽
        daily_traffic = (await session.execute(
            select(
                cast(RequestLog.created_at, Date).label("date"),
                func.count().label("cnt"),
                func.sum(case((RequestLog.status_code >= 400, 1), else_=0)).label("errors"),
                func.avg(RequestLog.duration_ms).label("avg_ms"),
            )
            .where(RequestLog.created_at >= period_start)
            .group_by(cast(RequestLog.created_at, Date))
            .order_by(cast(RequestLog.created_at, Date))
        )).all()

        # 상위 엔드포인트
        top_endpoints = (await session.execute(
            select(
                RequestLog.method,
                RequestLog.path,
                func.count().label("cnt"),
                func.avg(RequestLog.duration_ms).label("avg_ms"),
            )
            .where(RequestLog.created_at >= period_start)
            .group_by(RequestLog.method, RequestLog.path)
            .order_by(text("cnt DESC"))
            .limit(10)
        )).all()

        # 상태코드 분포
        status_dist = (await session.execute(
            select(RequestLog.status_code, func.count().label("cnt"))
            .where(RequestLog.created_at >= period_start)
            .group_by(RequestLog.status_code)
            .order_by(RequestLog.status_code)
        )).all()

        traffic_change = round((traffic_total - prev_traffic) / prev_traffic * 100, 1) if prev_traffic > 0 else None

        content["traffic"] = {
            "total_requests": traffic_total,
            "prev_total_requests": prev_traffic,
            "change_rate": traffic_change,
            "error_count": traffic_errors,
            "error_rate": error_rate,
            "avg_duration_ms": round(avg_duration, 1) if avg_duration else 0,
            "unique_ips": unique_ips,
            "daily_breakdown": [
                {"date": str(d), "count": c, "errors": int(e or 0), "avg_ms": round(float(a), 1) if a else 0}
                for d, c, e, a in daily_traffic
            ],
            "top_endpoints": [
                {"method": m, "path": p, "count": c, "avg_ms": round(float(a), 1) if a else 0}
                for m, p, c, a in top_endpoints
            ],
            "status_distribution": [{"code": s, "count": c} for s, c in status_dist],
        }

        change_str = ""
        if traffic_change is not None:
            change_str = f" (전기 대비 {'+'if traffic_change >= 0 else ''}{traffic_change}%)"
        summary_parts.append(f"트래픽: {traffic_total:,}건{change_str}, 에러율 {error_rate}%")
        summary_parts.append(f"방문자: {unique_ips}명 (고유 IP)")
    except Exception as e:
        logger.warning(f"트래픽 통계 수집 실패: {e}")
        content["traffic"] = {"error": str(e)[:200]}
        await session.rollback()

    # ── 3. NER / MLOps 통계 ──
    try:
        training_count = (await session.execute(
            select(func.count(NerTrainingSample.id)).where(
                NerTrainingSample.created_at >= period_start
            )
        )).scalar() or 0

        total_training = (await session.execute(
            select(func.count(NerTrainingSample.id))
        )).scalar() or 0

        avg_quality = (await session.execute(
            select(func.avg(NerTrainingSample.gpt_quality_score)).where(
                NerTrainingSample.created_at >= period_start,
                NerTrainingSample.gpt_quality_score.isnot(None),
            )
        )).scalar()

        prev_avg_quality = (await session.execute(
            select(func.avg(NerTrainingSample.gpt_quality_score)).where(
                NerTrainingSample.created_at >= prev_start,
                NerTrainingSample.created_at < prev_end,
                NerTrainingSample.gpt_quality_score.isnot(None),
            )
        )).scalar()

        active_model = (await session.execute(
            select(NerModelVersion)
            .where(NerModelVersion.is_active.is_(True))
            .limit(1)
        )).scalar_one_or_none()

        model_history = (await session.execute(
            select(NerModelVersion)
            .order_by(NerModelVersion.created_at.desc())
            .limit(5)
        )).scalars().all()

        # 일별 품질 추이
        quality_trend = (await session.execute(
            select(
                cast(NerTrainingSample.created_at, Date).label("date"),
                func.avg(NerTrainingSample.gpt_quality_score).label("avg_score"),
                func.count().label("cnt"),
            )
            .where(
                NerTrainingSample.created_at >= period_start,
                NerTrainingSample.gpt_quality_score.isnot(None),
            )
            .group_by(cast(NerTrainingSample.created_at, Date))
            .order_by(cast(NerTrainingSample.created_at, Date))
        )).all()

        content["mlops"] = {
            "new_training_samples": training_count,
            "total_training_samples": total_training,
            "avg_quality_score": round(avg_quality, 3) if avg_quality else None,
            "prev_avg_quality_score": round(prev_avg_quality, 3) if prev_avg_quality else None,
            "active_model": active_model.version if active_model else "base (기본 모델)",
            "active_model_f1": round(active_model.eval_f1_score, 4) if active_model and active_model.eval_f1_score else None,
            "model_history": [
                {
                    "version": m.version,
                    "f1": round(m.eval_f1_score, 4) if m.eval_f1_score else None,
                    "status": m.status,
                    "is_active": m.is_active,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in model_history
            ],
            "quality_trend": [
                {"date": str(d), "avg_score": round(float(s), 3), "count": c}
                for d, s, c in quality_trend
            ],
        }
        summary_parts.append(f"NER 학습 데이터: +{training_count}건 (총 {total_training:,}건)")
        if avg_quality:
            summary_parts.append(f"NER 평균 품질: {avg_quality:.3f}")
    except Exception as e:
        logger.warning(f"MLOps 통계 수집 실패: {e}")
        content["mlops"] = {"error": str(e)[:200]}
        await session.rollback()

    # ── 4. 시스템 상태 ──
    try:
        import psutil

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        content["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": mem.percent,
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_free_gb": round(disk.free / (1024**3), 1),
        }
    except Exception as e:
        logger.warning(f"시스템 상태 수집 실패: {e}")
        content["system"] = {"error": str(e)[:200]}
        await session.rollback()

    # ── 5. 에러 요약 ──
    try:
        top_errors = (await session.execute(
            select(
                RequestLog.path,
                RequestLog.status_code,
                func.count().label("cnt"),
            )
            .where(
                RequestLog.created_at >= period_start,
                RequestLog.status_code >= 400,
            )
            .group_by(RequestLog.path, RequestLog.status_code)
            .order_by(text("cnt DESC"))
            .limit(10)
        )).all()

        content["errors"] = {
            "total_errors": _traffic_errors,
            "top_errors": [
                {"path": p, "status_code": s, "count": c}
                for p, s, c in top_errors
            ],
        }
        if top_errors:
            summary_parts.append(f"주요 에러: {len(top_errors)}종")
    except Exception as e:
        content["errors"] = {"error": str(e)[:200]}
        await session.rollback()

    # ── 6. GPT-5 내러티브 요약 ──
    try:
        narrative = _generate_narrative(content, report_type, period_label)
        content["narrative"] = narrative
    except Exception as e:
        logger.warning(f"GPT-5 내러티브 생성 실패: {e}")
        content["narrative"] = None

    # ── 리포트 생성 ──
    period_str = now.strftime("%Y-%m-%d")
    title = f"[{period_label}] News Origin 운영 리포트 ({period_str})"
    summary = "\n".join(summary_parts) if summary_parts else "수집된 데이터 없음"

    content["period"] = {
        "start": period_start.isoformat(),
        "end": now.isoformat(),
        "type": report_type,
        "label": period_label,
        "days": period_days,
    }

    report = AdminReport(
        id=uuid.uuid4(),
        report_type=report_type,
        title=title,
        summary=summary,
        content_json=content,
        category="mixed",
        severity="info",
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    logger.info(f"정기 리포트 생성: {title}")
    return report


def _generate_narrative(content: dict, report_type: str, period_label: str) -> str | None:
    """GPT-5로 비전문가 관리자를 위한 내러티브 요약 생성"""
    from app.config import get_settings
    from app.services.azure_openai import call_gpt_sync

    settings = get_settings()
    if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
        return None

    parts = []

    crawling = content.get("crawling", {})
    if "error" not in crawling:
        parts.append(f"## 크롤링\n- 이번 기간 수집 기사: {crawling.get('total_articles', 0):,}건")
        prev = crawling.get("prev_total_articles")
        if prev:
            parts.append(f"- 이전 기간 수집: {prev:,}건 (변동률: {crawling.get('change_rate', 'N/A')}%)")
        cats = crawling.get("category_distribution", [])
        if isinstance(cats, list) and cats:
            parts.append("- 카테고리별: " + ", ".join(f"{c['category']} {c['count']}건" for c in cats))
        pubs = crawling.get("top_publishers", [])
        if pubs:
            parts.append("- 상위 언론사: " + ", ".join(f"{p['name']}({p['count']}건)" for p in pubs[:5]))

    traffic = content.get("traffic", {})
    if "error" not in traffic:
        parts.append(f"\n## 트래픽\n- 총 요청: {traffic.get('total_requests', 0):,}건 (이전: {traffic.get('prev_total_requests', 0):,}건)")
        parts.append(f"- 에러율: {traffic.get('error_rate', 0)}%, 평균 응답시간: {traffic.get('avg_duration_ms', 0)}ms")
        parts.append(f"- 고유 방문자: {traffic.get('unique_ips', 0)}명")

    mlops = content.get("mlops", {})
    if "error" not in mlops:
        parts.append(f"\n## MLOps (AI 키워드 추출)\n- 신규 학습 데이터: {mlops.get('new_training_samples', 0)}건 (총 {mlops.get('total_training_samples', 0):,}건)")
        q = mlops.get("avg_quality_score")
        pq = mlops.get("prev_avg_quality_score")
        if q:
            parts.append(f"- 이번 기간 평균 품질: {q} (이전: {pq if pq else 'N/A'})")
        parts.append(f"- 활성 모델: {mlops.get('active_model', 'base')}, F1: {mlops.get('active_model_f1', 'N/A')}")

    system = content.get("system", {})
    if "error" not in system:
        parts.append(f"\n## 시스템 리소스\n- CPU: {system.get('cpu_percent', 0)}%")
        parts.append(f"- 메모리: {system.get('memory_percent', 0)}% ({system.get('memory_used_gb', 0)}GB / {system.get('memory_total_gb', 0)}GB)")
        parts.append(f"- 디스크: {system.get('disk_percent', 0)}% (여유: {system.get('disk_free_gb', 0)}GB)")

    errors = content.get("errors", {})
    if "error" not in errors:
        total_e = errors.get("total_errors", 0)
        parts.append(f"\n## 에러: {total_e}건")
        top = errors.get("top_errors", [])
        if top:
            parts.append("- 상위: " + ", ".join(f"{e['path']}({e['status_code']}: {e['count']}건)" for e in top[:5]))

    data_text = "\n".join(parts)

    prompt = f"""당신은 뉴스 분석 플랫폼 'News Origin'의 운영 보고서 작성자입니다.
다음 {period_label} 운영 데이터를 바탕으로, IT 비전문가 관리자가 쉽게 이해할 수 있는 운영 현황 요약을 작성하세요.

{data_text}

작성 규칙:
1. 한국어로 작성, 800자 이내
2. 전문 용어는 괄호 안에 쉬운 설명 추가 (예: "F1 스코어(모델 정확도 지표)")
3. 핵심 수치 변화에 대한 해석 포함
4. 시스템이 안정적인지, 주의할 부분이 있는지 명확히 안내
5. 다음 기간에 관리자가 확인할 사항이 있으면 조언
6. 문단을 나눠 읽기 편하게 구성"""

    # GPT-5 reasoning 모델은 간헐적으로 빈 content를 반환할 수 있으므로 최대 2회 시도
    for attempt in range(2):
        try:
            result = call_gpt_sync(
                prompt=prompt,
                system_message="당신은 IT 서비스 운영 리포트 작성 전문가입니다. 비전문가도 이해할 수 있도록 명확하고 친절하게 작성합니다.",
                max_tokens=2048,
            )
            if result and result.strip():
                logger.info(f"GPT 내러티브 생성 완료 (시도 {attempt + 1}, {len(result)}자)")
                return result.strip()
            logger.warning(f"GPT 내러티브 빈 응답 (시도 {attempt + 1})")
        except Exception as e:
            logger.warning(f"GPT narrative failed (attempt {attempt + 1}): {e}")

    logger.warning("GPT 내러티브 생성 실패: 2회 시도 모두 빈 응답")
    return None


def generate_finetune_report(
    result: dict,
    current_f1: float | None,
    current_metric_type: str | None,
) -> str | None:
    """
    Fine-tuning 완료 리포트 생성 + 이메일 발송. Returns report_id or None.

    동기 wrapper — finetune 컨테이너에서 직접 호출, 자체 async engine 생성/폐기.
    (mlops_insight.py의 generate_deployment_insight()와 동일 패턴)
    """
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _generate():
        try:
            promoted = result.get("promoted", False)
            version = result.get("version", "unknown")
            f1 = result.get("f1", 0)
            precision = result.get("precision", 0)
            recall = result.get("recall", 0)

            # content_json 구성
            content: dict = {
                "training": {
                    "version": version,
                    "base_model": result.get("base_model", "klue/bert-base"),
                    "continual_learning": result.get("continual_learning", False),
                    "train_samples": result.get("train_samples", 0),
                    "val_samples": result.get("val_samples", 0),
                },
                "evaluation": {
                    "f1": f1,
                    "precision": precision,
                    "recall": recall,
                    "metric_type": result.get("metric_type", "entity"),
                },
                "quality_gate": {
                    "promoted": promoted,
                    "current_f1": current_f1,
                    "current_metric_type": current_metric_type,
                    "f1_improvement": round(f1 - current_f1, 4) if current_f1 is not None else None,
                    "decision_reason": (
                        f"비회귀 통과 ({f1:.4f} >= {current_f1:.4f})"
                        if promoted and current_f1 is not None
                        else "품질 기준 충족 (첫 모델)" if promoted
                        else f"회귀 감지 ({f1:.4f} < {current_f1:.4f})"
                        if current_f1 is not None
                        else f"절대 임계값 미달 (F1: {f1:.4f})"
                    ),
                },
            }

            # promoted인 경우 deployment_insight 조회
            if promoted:
                try:
                    async with factory() as db:
                        row = await db.execute(
                            select(NerModelVersion.deployment_insight).where(
                                NerModelVersion.version == version
                            )
                        )
                        insight = row.scalar_one_or_none()
                        if insight:
                            content["deployment_insight"] = insight
                except Exception as e:
                    logger.warning(f"Failed to fetch deployment insight: {e}")

            # GPT-5 내러티브 생성
            try:
                narrative = _generate_finetune_narrative(content, promoted)
                content["narrative"] = narrative
            except Exception as e:
                logger.warning(f"Fine-tuning narrative generation failed: {e}")
                content["narrative"] = None

            # AdminReport 생성
            title = f"[MLOps] Fine-tuning {'완료' if promoted else '결과'} — {version}"
            summary_parts = [
                f"모델: {version} (F1: {f1:.4f})",
                f"학습: {result.get('train_samples', 0)}건, 검증: {result.get('val_samples', 0)}건",
                f"승격: {'완료' if promoted else '거부'}" + (
                    f" (이전: {current_f1:.4f}, 개선: {f1 - current_f1:+.4f})"
                    if current_f1 is not None else ""
                ),
            ]

            async with factory() as db:
                report = AdminReport(
                    id=uuid.uuid4(),
                    report_type="mlops",
                    title=title,
                    summary="\n".join(summary_parts),
                    content_json=content,
                    category="mlops",
                    severity="info" if promoted else "warning",
                )
                db.add(report)
                await db.commit()
                await db.refresh(report)

                report_id = str(report.id)

                # 이메일 발송
                try:
                    from app.services.email_sender import send_report_email

                    sent = send_report_email(
                        title=report.title,
                        summary=report.summary,
                        report_type="mlops",
                        severity=report.severity,
                        report_id=report_id,
                        narrative=content.get("narrative"),
                    )
                    if sent:
                        report.email_sent = True
                        from datetime import datetime, timezone
                        report.email_sent_at = datetime.now(timezone.utc)
                        await db.commit()
                except Exception as e:
                    logger.warning(f"Fine-tuning report email failed: {e}")
                    try:
                        report.email_error = str(e)[:200]
                        await db.commit()
                    except Exception:
                        pass

            logger.info(f"Fine-tuning report generated: {title}")
            return report_id
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_generate())
    except Exception as e:
        logger.error(f"generate_finetune_report failed: {e}")
        return None
    finally:
        loop.close()


def _generate_finetune_narrative(content: dict, promoted: bool) -> str | None:
    """GPT-5로 Fine-tuning 결과 비전문가 관리자용 내러티브 생성"""
    from app.config import get_settings
    from app.services.azure_openai import call_gpt_sync

    settings = get_settings()
    if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
        return None

    training = content.get("training", {})
    evaluation = content.get("evaluation", {})
    quality_gate = content.get("quality_gate", {})

    data_text = f"""## Fine-tuning 결과
- 모델 버전: {training.get('version', 'N/A')}
- 기반 모델: {training.get('base_model', 'N/A')}
- 이어 학습 여부: {'예' if training.get('continual_learning') else '아니오'}
- 학습 데이터: {training.get('train_samples', 0)}건, 검증 데이터: {training.get('val_samples', 0)}건

## 평가 결과 ({evaluation.get('metric_type', 'entity')}-level)
- F1 Score: {evaluation.get('f1', 0):.4f}
- Precision: {evaluation.get('precision', 0):.4f}
- Recall: {evaluation.get('recall', 0):.4f}

## 품질 검증
- 승격 여부: {'승격 완료' if promoted else '승격 거부'}
- 이전 모델 F1: {quality_gate.get('current_f1', 'N/A')}
- F1 개선폭: {quality_gate.get('f1_improvement', 'N/A')}
- 판정 사유: {quality_gate.get('decision_reason', 'N/A')}"""

    prompt = f"""당신은 뉴스 분석 플랫폼 'News Origin'의 AI 키워드 추출 모델 학습 결과 리포트 작성자입니다.
다음 Fine-tuning 결과를 바탕으로, IT 비전문가 관리자가 쉽게 이해할 수 있는 요약을 작성하세요.

{data_text}

작성 규칙:
1. 한국어로 작성, 500자 이내
2. 전문 용어는 괄호 안에 쉬운 설명 추가 (예: "F1 스코어(모델 정확도 지표)")
3. 학습이 잘 되었는지, 이전 대비 개선되었는지 명확히 안내
4. {'모델이 자동으로 교체되었다는 점을 안내' if promoted else '모델이 교체되지 않았으며 이전 모델을 계속 사용한다는 점을 안내'}
5. 관리자가 추가 조치가 필요한지 여부를 알려주세요"""

    for attempt in range(2):
        try:
            result = call_gpt_sync(
                prompt=prompt,
                system_message="당신은 AI 모델 학습 결과를 비전문가에게 설명하는 전문가입니다. 명확하고 친절하게 작성합니다.",
                max_tokens=1024,
            )
            if result and result.strip():
                logger.info(f"Fine-tuning narrative generated (attempt {attempt + 1}, {len(result)}chars)")
                return result.strip()
            logger.warning(f"Fine-tuning narrative empty response (attempt {attempt + 1})")
        except Exception as e:
            logger.warning(f"Fine-tuning narrative failed (attempt {attempt + 1}): {e}")

    logger.warning("Fine-tuning narrative generation failed after 2 attempts")
    return None


async def generate_alert_report(
    session: AsyncSession,
    category: str,
    severity: str,
    title: str,
    summary: str,
    details: dict,
) -> AdminReport:
    """비정기 알림 리포트 생성 — 원인·대응 가이드 포함"""

    # 카테고리별 대응 가이드 (비전문가 관리자용)
    recommendations = {
        "traffic": "에러 로그를 확인하세요. 특정 페이지에서 반복적으로 에러가 발생한다면 개발팀에 문의하세요. 일시적인 문제라면 자동 복구될 수 있습니다.",
        "traffic_spike": "갑작스러운 방문자 증가입니다. 정상적인 트래픽인지 확인하세요. 서버 성능에 영향이 없다면 긍정적인 신호입니다.",
        "system": "디스크 공간이 부족합니다. 오래된 로그 파일이나 불필요한 데이터를 정리하세요. 90일이 지난 기사는 자동으로 삭제됩니다.",
        "system_memory": "메모리 사용량이 높습니다. 서버를 재시작하면 일시적으로 해소될 수 있습니다. 반복되면 서버 사양 검토가 필요합니다.",
    }

    enriched = {
        **details,
        "recommendation": recommendations.get(category, "시스템 관리자에게 문의하세요."),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }

    report = AdminReport(
        id=uuid.uuid4(),
        report_type="alert",
        title=title,
        summary=summary,
        content_json=enriched,
        category=category,
        severity=severity,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    logger.info(f"알림 리포트 생성: [{severity}] {title}")
    return report
