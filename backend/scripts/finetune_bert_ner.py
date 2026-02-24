"""
# finetune_bert_ner.py - BERT NER Fine-tuning Script
# Version: 0.4.0
# Description: GPT 교정 데이터로 BERT NER 모델 fine-tuning
# Changes:
#   - 0.4.0: 누적 학습, seqeval entity-level F1, 샘플 상한, 품질 임계값 분리,
#             continual learning, adaptive LR, early stopping, stratified split
#   - 0.3.0: 이벤트 루프 충돌 해결 — DB 작업마다 자체 엔진 생성/폐기
#   - 0.2.0: 모델 승격 후 GPT-5 배포 인사이트 자동 생성
#   - 0.1.0: DB 학습 데이터 로드, HuggingFace Trainer NER fine-tuning, 모델 저장
#
# 실행 방법:
#   docker compose run finetune                    # 프로덕션 (별도 컨테이너)
#   python -m scripts.finetune_bert_ner            # 개발 환경
#   python -m scripts.finetune_bert_ner --dry-run  # 데이터만 확인
#
# 예상 소요 시간 (i7-9750H CPU):
#   500건: ~30분, 2000건: ~2시간
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 프로젝트 루트를 sys.path에 추가 (스크립트 직접 실행 대응)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def load_training_data() -> list[dict]:
    """DB에서 NER 학습 데이터 로드 — 누적 데이터, 고품질 우선, 상한 적용"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import select, func as sa_func
    from app.config import get_settings
    from app.models.ner_training import NerTrainingSample

    settings = get_settings()
    min_quality = settings.ner_training_min_quality
    max_samples = settings.ner_training_max_samples
    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _load():
        async with factory() as db:
            # 누적 전체 데이터 — is_used_for_training 필터 제거
            # 고품질 우선 정렬 + 상한 적용
            result = await db.execute(
                select(NerTrainingSample).where(
                    NerTrainingSample.gpt_quality_score >= min_quality,
                ).order_by(
                    NerTrainingSample.gpt_quality_score.desc()
                ).limit(max_samples)
            )
            samples = result.scalars().all()

            # 전체 적격 샘플 수 (상한 적용 전)
            total_result = await db.execute(
                select(sa_func.count()).select_from(NerTrainingSample).where(
                    NerTrainingSample.gpt_quality_score >= min_quality,
                )
            )
            total_eligible = total_result.scalar_one()

            return [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "bio_tags": s.bio_tags,
                    "quality_score": s.gpt_quality_score,
                }
                for s in samples
            ], total_eligible

    loop = asyncio.new_event_loop()
    try:
        data, total_eligible = loop.run_until_complete(_load())
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()

    logger.info(
        f"Loaded {len(data)} samples (min_quality={min_quality}, "
        f"max_samples={max_samples}, total_eligible={total_eligible})"
    )
    return data


def mark_samples_used(sample_ids: list[str]) -> None:
    """학습에 사용된 샘플을 is_used_for_training=True로 업데이트"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import update
    from app.config import get_settings
    from app.models.ner_training import NerTrainingSample
    import uuid

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _mark():
        async with factory() as db:
            await db.execute(
                update(NerTrainingSample)
                .where(NerTrainingSample.id.in_([uuid.UUID(sid) for sid in sample_ids]))
                .values(is_used_for_training=True)
            )
            await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_mark())
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()


def save_model_version(version: str, model_path: str, samples_count: int,
                       f1: float, precision: float, recall: float,
                       base_model: str, metric_type: str = "entity") -> None:
    """ner_model_versions 테이블에 새 모델 버전 기록"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import get_settings
    from app.models.ner_training import NerModelVersion

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _save():
        async with factory() as db:
            record = NerModelVersion(
                version=version,
                base_model=base_model,
                model_path=model_path,
                training_samples_count=samples_count,
                eval_f1_score=f1,
                eval_precision=precision,
                eval_recall=recall,
                metric_type=metric_type,
                status="ready",
                is_active=False,
            )
            db.add(record)
            await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_save())
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()


def build_label_list(data: list[dict]) -> list[str]:
    """학습 데이터에서 고유 라벨 목록 추출"""
    labels = set()
    for sample in data:
        for _, tag in sample["bio_tags"]:
            labels.add(tag)
    labels = sorted(labels)
    # O 태그를 첫 번째로
    if "O" in labels:
        labels.remove("O")
        labels = ["O"] + labels
    return labels


def prepare_dataset(data: list[dict], tokenizer, label2id: dict, max_length: int = 64):
    """학습 데이터를 HuggingFace Dataset 형식으로 변환"""
    import torch
    from torch.utils.data import Dataset

    class NERDataset(Dataset):
        def __init__(self, samples, tokenizer, label2id, max_length):
            self.samples = samples
            self.tokenizer = tokenizer
            self.label2id = label2id
            self.max_length = max_length

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            sample = self.samples[idx]
            title = sample["title"]
            bio_tags = sample["bio_tags"]

            # 문자 단위 BIO 태그 → 문자 리스트
            chars = [pair[0] for pair in bio_tags]
            char_labels = [pair[1] for pair in bio_tags]

            # 토크나이저 적용
            encoding = self.tokenizer(
                title,
                max_length=self.max_length,
                padding="max_length",
                truncation=True,
                return_offsets_mapping=True,
                return_tensors="pt",
            )

            # offset_mapping으로 토큰 → 문자 매핑 → 라벨 할당
            offsets = encoding["offset_mapping"].squeeze().tolist()
            labels = []
            for offset in offsets:
                start, end = offset
                if start == 0 and end == 0:
                    # [CLS], [SEP], [PAD] 등 special tokens
                    labels.append(-100)
                else:
                    # 토큰의 첫 문자에 해당하는 라벨 사용
                    if start < len(char_labels):
                        label_str = char_labels[start]
                        labels.append(self.label2id.get(label_str, self.label2id.get("O", 0)))
                    else:
                        labels.append(-100)

            return {
                "input_ids": encoding["input_ids"].squeeze(),
                "attention_mask": encoding["attention_mask"].squeeze(),
                "labels": torch.tensor(labels, dtype=torch.long),
            }

    return NERDataset(data, tokenizer, label2id, max_length)


def compute_metrics(eval_pred, id2label):
    """검증 세트 평가 메트릭 — seqeval entity-level F1"""
    import numpy as np
    from seqeval.metrics import f1_score, precision_score, recall_score

    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=2)

    true_labels = []
    pred_labels = []

    for pred_seq, label_seq in zip(predictions, labels):
        true_seq = []
        pred_seq_filtered = []
        for p, l in zip(pred_seq, label_seq):
            if l == -100:
                continue
            true_seq.append(id2label.get(l, "O"))
            pred_seq_filtered.append(id2label.get(p, "O"))
        true_labels.append(true_seq)
        pred_labels.append(pred_seq_filtered)

    return {
        "precision": precision_score(true_labels, pred_labels),
        "recall": recall_score(true_labels, pred_labels),
        "f1": f1_score(true_labels, pred_labels),
    }


def _get_entity_class(sample: dict) -> str:
    """샘플의 주요 엔터티 유형 결정 (층화 분할용)"""
    type_counts: dict[str, int] = {}
    for _, tag in sample["bio_tags"]:
        if tag.startswith("B-"):
            entity_type = tag[2:]
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
    if not type_counts:
        return "O"
    return max(type_counts, key=type_counts.get)


def stratified_split(data: list[dict], test_ratio: float = 0.2):
    """엔터티 유형 기반 층화 train/val 분할"""
    import random
    from collections import Counter

    # 엔터티 유형별 그룹화
    class_indices: dict[str, list[int]] = {}
    for i, sample in enumerate(data):
        cls = _get_entity_class(sample)
        class_indices.setdefault(cls, []).append(i)

    # 희소 클래스 확인 (2건 미만 → 층화 불가)
    class_counts = Counter(_get_entity_class(s) for s in data)
    sparse_classes = {cls for cls, count in class_counts.items() if count < 2}

    if sparse_classes and len(sparse_classes) == len(class_counts):
        # 모든 클래스가 희소 → random split fallback
        logger.warning("All entity classes are sparse (<2 samples), using random split")
        random.shuffle(data)
        split_idx = int(len(data) * (1 - test_ratio))
        return data[:split_idx], data[split_idx:]

    train_indices = []
    val_indices = []

    for cls, indices in class_indices.items():
        random.shuffle(indices)
        if cls in sparse_classes:
            # 희소 클래스는 전부 train에 포함
            train_indices.extend(indices)
            continue
        n_val = max(1, int(len(indices) * test_ratio))
        val_indices.extend(indices[:n_val])
        train_indices.extend(indices[n_val:])

    train_data = [data[i] for i in train_indices]
    val_data = [data[i] for i in val_indices]

    # 셔플
    random.shuffle(train_data)
    random.shuffle(val_data)

    logger.info(f"Stratified split — entity class distribution: {dict(class_counts)}")
    return train_data, val_data


def _resolve_base_model(settings) -> tuple[str, bool]:
    """
    학습 시작 모델 결정 — continual learning 지원

    Returns:
        (model_path, is_continual): 모델 경로와 continual learning 여부
    """
    from app.services.model_manager import get_active_model_path

    if not settings.ner_continual_learning:
        return settings.bert_model_name, False

    active_path = get_active_model_path()
    if active_path is None:
        logger.info("No active model found, using base model")
        return settings.bert_model_name, False

    # 라벨 호환성은 모델 로딩 후 확인
    logger.info(f"Continual learning from active model: {active_path}")
    return active_path, True


def run_finetune(dry_run: bool = False) -> dict:
    """
    BERT NER fine-tuning 실행

    Returns:
        {"status": "ok", "version": "v20260224", "f1": 0.85, ...}
    """
    from app.config import get_settings

    settings = get_settings()

    # 1. 학습 데이터 로드 (누적 전체, 고품질 우선, 상한 적용)
    logger.info("Loading training data from DB...")
    data = load_training_data()
    logger.info(f"Loaded {len(data)} training samples")

    if len(data) < 10:
        logger.warning(f"Not enough training data ({len(data)} < 10), aborting")
        return {"status": "insufficient_data", "samples": len(data)}

    if dry_run:
        labels = build_label_list(data)
        logger.info(f"[DRY RUN] Labels: {labels}")
        logger.info(f"[DRY RUN] Sample titles: {[d['title'][:50] for d in data[:5]]}")
        logger.info(f"[DRY RUN] Quality range: {data[-1]['quality_score']:.2f} ~ {data[0]['quality_score']:.2f}")
        return {"status": "dry_run", "samples": len(data), "labels": labels}

    # 2. 라벨 목록 구성
    labels = build_label_list(data)
    label2id = {l: i for i, l in enumerate(labels)}
    id2label = {i: l for l, i in label2id.items()}
    logger.info(f"Labels ({len(labels)}): {labels}")

    # 3. 모델 + 토크나이저 로딩 (continual learning 지원)
    from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer, EarlyStoppingCallback

    base_model, is_continual = _resolve_base_model(settings)
    logger.info(f"Loading model: {base_model} (continual={is_continual})")

    try:
        tokenizer = AutoTokenizer.from_pretrained(base_model)
        model = AutoModelForTokenClassification.from_pretrained(
            base_model,
            num_labels=len(labels),
            id2label=id2label,
            label2id=label2id,
        )
    except Exception as e:
        if is_continual:
            # 라벨 불일치 등 오류 시 base 모델로 fallback
            logger.warning(f"Continual learning failed ({e}), falling back to base model")
            base_model = settings.bert_model_name
            is_continual = False
            tokenizer = AutoTokenizer.from_pretrained(base_model)
            model = AutoModelForTokenClassification.from_pretrained(
                base_model,
                num_labels=len(labels),
                id2label=id2label,
                label2id=label2id,
            )
        else:
            raise

    # 4. Stratified Train/Val 분할
    train_data, val_data = stratified_split(data, test_ratio=0.2)
    logger.info(f"Train: {len(train_data)}, Val: {len(val_data)}")

    train_dataset = prepare_dataset(train_data, tokenizer, label2id)
    val_dataset = prepare_dataset(val_data, tokenizer, label2id)

    # 5. 모델 버전 + 출력 디렉토리
    from app.services.model_manager import get_next_version

    version = get_next_version()
    output_dir = Path(settings.ner_model_base_dir) / version
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir} (version: {version})")

    # 6. Adaptive learning rate
    learning_rate = settings.ner_learning_rate_finetune if is_continual else settings.ner_learning_rate_base
    logger.info(f"Learning rate: {learning_rate} ({'finetune' if is_continual else 'base'})")

    # 7. Training with early stopping
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=settings.ner_max_epochs,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_steps=10,
        max_grad_norm=1.0,
        learning_rate=learning_rate,
        weight_decay=0.01,
        warmup_ratio=0.1,
        use_cpu=True,  # CPU 전용 (AMD GPU, CUDA 미지원)
        save_total_limit=2,
        report_to="none",
    )

    callbacks = []
    if settings.ner_early_stopping_patience > 0:
        callbacks.append(
            EarlyStoppingCallback(early_stopping_patience=settings.ner_early_stopping_patience)
        )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=lambda p: compute_metrics(p, id2label),
        callbacks=callbacks,
    )

    logger.info(f"Starting fine-tuning (max_epochs={settings.ner_max_epochs}, "
                f"early_stopping_patience={settings.ner_early_stopping_patience})...")
    trainer.train()

    # 8. 최종 평가
    eval_results = trainer.evaluate()
    f1 = eval_results.get("eval_f1", 0.0)
    precision = eval_results.get("eval_precision", 0.0)
    recall = eval_results.get("eval_recall", 0.0)
    logger.info(f"Evaluation (entity-level): F1={f1:.4f}, Precision={precision:.4f}, Recall={recall:.4f}")

    # 9. 모델 저장
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    logger.info(f"Model saved to {output_dir}")

    # 10. DB에 모델 버전 기록 (metric_type="entity")
    save_model_version(
        version=version,
        model_path=str(output_dir),
        samples_count=len(train_data),
        f1=f1,
        precision=precision,
        recall=recall,
        base_model=base_model,
        metric_type="entity",
    )

    # 11. 학습 데이터 사용 완료 표시
    sample_ids = [d["id"] for d in data]
    mark_samples_used(sample_ids)

    # 12. Quality gate 확인 + 자동 승격
    from app.services.model_manager import should_promote, promote_model

    # 현재 active 모델의 F1 + metric_type 조회
    current_f1 = None
    current_metric_type = None
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy import select
        from app.models.ner_training import NerModelVersion

        async def _get_active_info():
            _engine = create_async_engine(settings.database_url, pool_size=2)
            _factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
            try:
                async with _factory() as db:
                    result = await db.execute(
                        select(
                            NerModelVersion.eval_f1_score,
                            NerModelVersion.metric_type,
                        ).where(
                            NerModelVersion.is_active == True  # noqa: E712
                        )
                    )
                    row = result.first()
                    if row:
                        return row[0], row[1]
                    return None, None
            finally:
                await _engine.dispose()

        loop = asyncio.new_event_loop()
        try:
            current_f1, current_metric_type = loop.run_until_complete(_get_active_info())
        finally:
            loop.close()
    except Exception:
        pass

    promoted = should_promote(f1, current_f1, current_metric_type=current_metric_type)
    if promoted:
        logger.info(f"Quality gate passed (new={f1:.4f}, current={current_f1}, "
                     f"metric_type_transition={current_metric_type}→entity), promoting {version}")
        promote_model(version)

        # 배포 인사이트 생성 (GPT-5)
        try:
            from app.services.mlops_insight import generate_deployment_insight
            insight = generate_deployment_insight(
                version=version,
                new_f1=f1,
                prev_f1=current_f1,
                train_count=len(train_data),
            )
            if insight:
                logger.info(f"Deployment insight generated for {version}")
            else:
                logger.warning(f"Deployment insight returned empty for {version}")
        except Exception as e:
            logger.warning(f"Insight generation failed (non-critical): {e}")

        # 키워드 재추출 태스크 자동 트리거
        try:
            from celery import Celery
            _celery = Celery(broker=settings.celery_broker_url)
            _celery.send_task('app.workers.tasks.reextract_keywords_batch')
            logger.info(f"reextract_keywords_batch task triggered after {version} promotion")
        except Exception as e:
            logger.warning(f"Failed to trigger reextract task (non-critical): {e}")

        try:
            from app.services.webhook import send_webhook
            send_webhook(
                title="NER 모델 승격 완료",
                description=(
                    f"버전: {version}\n"
                    f"F1: {f1:.4f} (이전: {current_f1 or 'N/A'})\n"
                    f"메트릭: entity-level (seqeval)\n"
                    f"학습 데이터: {len(train_data)}건\n"
                    f"Continual learning: {'예' if is_continual else '아니오'}\n"
                    f"키워드 재추출 태스크 자동 트리거됨."
                ),
                color=0x2ECC71,
            )
        except Exception:
            pass
    else:
        logger.warning(f"Quality gate failed (new={f1:.4f}, current={current_f1}, "
                        f"metric_type={current_metric_type}), model saved but NOT promoted")

    return {
        "status": "ok",
        "version": version,
        "f1": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "metric_type": "entity",
        "train_samples": len(train_data),
        "val_samples": len(val_data),
        "continual_learning": is_continual,
        "base_model": base_model,
        "promoted": promoted,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BERT NER Fine-tuning")
    parser.add_argument("--dry-run", action="store_true", help="데이터 확인만 (학습 미실행)")
    args = parser.parse_args()

    result = run_finetune(dry_run=args.dry_run)
    logger.info(f"Result: {result}")
