"""
# model_manager.py - BERT NER Model Version Manager
# Version: 0.3.0
# Description: 모델 버전 관리, 심볼릭 링크 전환, quality gate 검증
# Changes:
#   - 0.3.0: 날짜 기반 버전 (v20260224), should_promote metric_type 인식
#   - 0.2.0: promote_model 자체 DB 엔진 생성으로 이벤트 루프 충돌 해결
#   - 0.1.0: 버전 조회, 승격, 롤백, quality gate
#
# 디렉토리 구조:
# /app/models/bert-ner/
# +-- v0004/          (기존 sequential 버전)
# +-- v20260224/      (날짜 기반 버전)
# +-- v20260224_2/    (같은 날 2번째)
# +-- active -> v20260224 (심볼릭 링크)
"""

import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 버전 디렉토리 패턴: v + 숫자 (v0001, v20260224, v20260224_2)
_VERSION_PATTERN = re.compile(r"^v\d+(_\d+)?$")

KST = timezone(timedelta(hours=9))


def _is_version_dir(name: str) -> bool:
    """버전 디렉토리 이름인지 확인 (v0001, v20260224, v20260224_2 등)"""
    return bool(_VERSION_PATTERN.match(name))


def _get_base_dir() -> Path:
    """모델 베이스 디렉토리 반환"""
    from app.config import get_settings
    return Path(get_settings().ner_model_base_dir)


def get_current_version() -> str:
    """
    현재 활성 모델 버전 반환

    우선순위:
    1. active 심볼릭 링크가 가리키는 디렉토리명
    2. BERT_NER_MODEL_PATH 환경변수
    3. "base" (klue/bert-base 기본 모델)
    """
    base_dir = _get_base_dir()
    active_link = base_dir / "active"

    if active_link.is_symlink():
        target = active_link.resolve()
        return target.name

    from app.config import get_settings
    settings = get_settings()
    if settings.bert_ner_model_path:
        return Path(settings.bert_ner_model_path).name

    return "base"


def get_active_model_path() -> Optional[str]:
    """
    활성 모델의 전체 경로 반환

    active 심볼릭 링크가 있으면 해당 경로, 없으면 None
    """
    base_dir = _get_base_dir()
    active_link = base_dir / "active"

    if active_link.is_symlink() and active_link.resolve().exists():
        return str(active_link.resolve())

    return None


def get_next_version() -> str:
    """
    다음 모델 버전 문자열 생성 (날짜 기반)

    형식: v20260224 (첫 번째), v20260224_2 (같은 날 두 번째), ...
    """
    base_dir = _get_base_dir()
    today = datetime.now(KST).strftime("%Y%m%d")
    base_version = f"v{today}"

    if not base_dir.exists():
        return base_version

    # 오늘 날짜로 시작하는 기존 버전 찾기
    existing_today = []
    for d in base_dir.iterdir():
        if d.is_dir() and d.name == base_version:
            existing_today.append(1)
        elif d.is_dir() and d.name.startswith(f"{base_version}_"):
            suffix = d.name[len(base_version) + 1:]
            if suffix.isdigit():
                existing_today.append(int(suffix))

    if not existing_today:
        return base_version

    return f"{base_version}_{max(existing_today) + 1}"


def _list_version_dirs(base_dir: Path) -> list[str]:
    """버전 디렉토리 목록 (정렬됨) — 기존 v0001과 새 v20260224 모두 포함"""
    if not base_dir.exists():
        return []
    return sorted([
        d.name for d in base_dir.iterdir()
        if d.is_dir() and _is_version_dir(d.name)
    ])


def promote_model(version: str, session_factory=None) -> bool:
    """
    모델 승격: 심볼릭 링크 전환 + DB 상태 업데이트

    Args:
        version: 승격할 모델 버전 (예: "v20260224")
        session_factory: (deprecated, 무시됨) 자체 엔진 생성으로 대체

    Returns:
        성공 여부
    """
    import asyncio

    base_dir = _get_base_dir()
    model_dir = base_dir / version
    active_link = base_dir / "active"

    if not model_dir.exists():
        logger.error(f"Model directory does not exist: {model_dir}")
        return False

    try:
        # 심볼릭 링크 원자적 교체
        temp_link = base_dir / f"active_tmp_{os.getpid()}"
        os.symlink(model_dir, temp_link)
        os.replace(temp_link, active_link)
        logger.info(f"Model active link updated: {version}")
    except Exception as e:
        logger.error(f"Failed to update symlink: {e}")
        return False

    # DB 상태 업데이트 — 자체 엔진/세션 생성 (이벤트 루프 충돌 방지)
    async def _update_db():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy import update
        from app.config import get_settings
        from app.models.ner_training import NerModelVersion

        engine = create_async_engine(get_settings().database_url, pool_size=2)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as db:
                # 기존 active 모델 retired 처리
                await db.execute(
                    update(NerModelVersion)
                    .where(NerModelVersion.is_active == True)  # noqa: E712
                    .values(is_active=False, status="retired")
                )
                # 새 모델 active 처리
                await db.execute(
                    update(NerModelVersion)
                    .where(NerModelVersion.version == version)
                    .values(is_active=True, status="active")
                )
                await db.commit()
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_update_db())
    except Exception as e:
        logger.error(f"DB update failed during model promotion: {e}")
    finally:
        loop.close()

    return True


def rollback_model() -> bool:
    """
    이전 active 모델로 롤백

    Returns:
        성공 여부
    """
    base_dir = _get_base_dir()
    versions = _list_version_dirs(base_dir)

    if len(versions) < 2:
        logger.error("Not enough versions to rollback")
        return False

    current = get_current_version()
    # 현재 버전 직전 버전으로 롤백
    try:
        current_idx = versions.index(current)
        if current_idx == 0:
            logger.error("Already at the oldest version")
            return False
        prev_version = versions[current_idx - 1]
    except ValueError:
        # 현재 버전을 찾을 수 없으면 마지막에서 두 번째로 롤백
        prev_version = versions[-2]

    logger.warning(f"Rolling back model from {current} to {prev_version}")
    return promote_model(prev_version)


def should_promote(
    new_f1: float,
    current_f1: Optional[float],
    min_f1_threshold: float = 0.90,
    current_metric_type: Optional[str] = None,
) -> bool:
    """
    Quality gate: 새 모델이 승격 조건을 충족하는지 검증

    판정 기준:
        1. 절대 임계값: F1 >= min_f1_threshold (기본 0.90)
        2. 비회귀: F1 >= 현재 active 모델의 F1 (같거나 높으면 승격)

    Args:
        new_f1: 새 모델의 검증 F1 점수
        current_f1: 현재 활성 모델의 F1 점수 (없으면 None)
        min_f1_threshold: 최소 F1 절대 임계값
        current_metric_type: 현재 모델의 메트릭 유형 ("token"|"entity"|None)

    Returns:
        승격 여부
    """
    # 절대 임계값 미달 시 무조건 탈락
    if new_f1 < min_f1_threshold:
        return False

    if current_f1 is None:
        # 기존 모델이 없으면 (base model) 절대 임계값만 통과하면 승격
        return True

    # 메트릭 유형 전환 (token→entity): 직접 비교 불가, 절대 임계값만 적용
    if current_metric_type != "entity":
        return True

    # 비회귀: 현재 모델 대비 같거나 높으면 승격
    return new_f1 >= current_f1


def cleanup_old_versions(keep_count: int = 3) -> int:
    """
    오래된 모델 버전 정리 (active + 최근 keep_count개 유지)

    Returns:
        삭제된 버전 수
    """
    import shutil

    base_dir = _get_base_dir()
    if not base_dir.exists():
        return 0

    current = get_current_version()
    versions = _list_version_dirs(base_dir)

    if len(versions) <= keep_count:
        return 0

    to_remove = versions[:-keep_count]
    removed = 0
    for v in to_remove:
        if v == current:
            continue  # active 모델은 절대 삭제 금지
        try:
            shutil.rmtree(base_dir / v)
            removed += 1
            logger.info(f"Removed old model version: {v}")
        except Exception as e:
            logger.warning(f"Failed to remove model version {v}: {e}")

    return removed
