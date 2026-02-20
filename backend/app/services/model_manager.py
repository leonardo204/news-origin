"""
# model_manager.py - BERT NER Model Version Manager
# Version: 0.1.0
# Description: 모델 버전 관리, 심볼릭 링크 전환, quality gate 검증
# Changes:
#   - 0.1.0: 버전 조회, 승격, 롤백, quality gate
#
# 디렉토리 구조:
# /app/models/bert-ner/
# +-- v0001/          (klue/bert-base baseline)
# +-- v0002/          (1차 fine-tune)
# +-- active -> v0002 (심볼릭 링크)
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
    """다음 모델 버전 문자열 생성 (v0001, v0002, ...)"""
    base_dir = _get_base_dir()
    if not base_dir.exists():
        return "v0001"

    existing = []
    for d in base_dir.iterdir():
        if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit():
            existing.append(int(d.name[1:]))

    if not existing:
        return "v0001"

    return f"v{max(existing) + 1:04d}"


def promote_model(version: str, session_factory=None) -> bool:
    """
    모델 승격: 심볼릭 링크 전환 + DB 상태 업데이트

    Args:
        version: 승격할 모델 버전 (예: "v0002")
        session_factory: DB 세션 팩토리

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

    # DB 상태 업데이트
    if session_factory:
        async def _update_db():
            from sqlalchemy import select, update
            from app.models.ner_training import NerModelVersion

            async with session_factory() as db:
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

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_update_db())
        except Exception as e:
            logger.error(f"DB update failed during model promotion: {e}")
        finally:
            loop.close()

    return True


def rollback_model(session_factory=None) -> bool:
    """
    이전 active 모델로 롤백

    Returns:
        성공 여부
    """
    import asyncio

    base_dir = _get_base_dir()

    # 버전 디렉토리 목록 (숫자순 정렬)
    versions = sorted([
        d.name for d in base_dir.iterdir()
        if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
    ])

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
    return promote_model(prev_version, session_factory)


def should_promote(
    new_f1: float,
    current_f1: Optional[float],
    min_improvement: float = 0.01,
) -> bool:
    """
    Quality gate: 새 모델이 승격 조건을 충족하는지 검증

    Args:
        new_f1: 새 모델의 검증 F1 점수
        current_f1: 현재 활성 모델의 F1 점수 (없으면 None)
        min_improvement: 최소 F1 개선 폭

    Returns:
        승격 여부
    """
    if current_f1 is None:
        # 기존 모델이 없으면 (base model) F1 > 0.5 이면 승격
        return new_f1 > 0.5

    return new_f1 >= current_f1 + min_improvement


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

    versions = sorted([
        d.name for d in base_dir.iterdir()
        if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
    ])

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
