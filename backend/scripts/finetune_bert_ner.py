"""
# finetune_bert_ner.py - BERT NER Fine-tuning Script
# Version: 0.1.0
# Description: GPT 교정 데이터로 BERT NER 모델 fine-tuning
# Changes:
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


def load_training_data(min_quality: float = 0.7) -> list[dict]:
    """DB에서 NER 학습 데이터 로드"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import select
    from app.config import get_settings
    from app.models.ner_training import NerTrainingSample

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _load():
        async with factory() as db:
            result = await db.execute(
                select(NerTrainingSample).where(
                    NerTrainingSample.gpt_quality_score >= min_quality,
                    NerTrainingSample.is_used_for_training == False,  # noqa: E712
                ).order_by(NerTrainingSample.created_at)
            )
            samples = result.scalars().all()
            return [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "bio_tags": s.bio_tags,
                    "quality_score": s.gpt_quality_score,
                }
                for s in samples
            ]

    loop = asyncio.new_event_loop()
    try:
        data = loop.run_until_complete(_load())
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()

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
                       base_model: str) -> None:
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
    """검증 세트 평가 메트릭 (seqeval)"""
    import numpy as np

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

    # 간단한 토큰 수준 F1 계산 (seqeval 없이)
    tp = fp = fn = 0
    for true_seq, pred_seq in zip(true_labels, pred_labels):
        for t, p in zip(true_seq, pred_seq):
            if t != "O" and p != "O":
                if t == p:
                    tp += 1
                else:
                    fp += 1
                    fn += 1
            elif t != "O":
                fn += 1
            elif p != "O":
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def run_finetune(dry_run: bool = False) -> dict:
    """
    BERT NER fine-tuning 실행

    Returns:
        {"status": "ok", "version": "v0002", "f1": 0.85, ...}
    """
    from app.config import get_settings

    settings = get_settings()

    # 1. 학습 데이터 로드
    logger.info("Loading training data from DB...")
    data = load_training_data(min_quality=settings.ner_eval_min_quality)
    logger.info(f"Loaded {len(data)} training samples")

    if len(data) < 10:
        logger.warning(f"Not enough training data ({len(data)} < 10), aborting")
        return {"status": "insufficient_data", "samples": len(data)}

    if dry_run:
        labels = build_label_list(data)
        logger.info(f"[DRY RUN] Labels: {labels}")
        logger.info(f"[DRY RUN] Sample titles: {[d['title'][:50] for d in data[:5]]}")
        return {"status": "dry_run", "samples": len(data), "labels": labels}

    # 2. 라벨 목록 구성
    labels = build_label_list(data)
    label2id = {l: i for i, l in enumerate(labels)}
    id2label = {i: l for l, i in label2id.items()}
    logger.info(f"Labels ({len(labels)}): {labels}")

    # 3. 모델 + 토크나이저 로딩
    from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer

    base_model = settings.bert_model_name
    logger.info(f"Loading base model: {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForTokenClassification.from_pretrained(
        base_model,
        num_labels=len(labels),
        id2label=id2label,
        label2id=label2id,
    )

    # 4. Train/Val 분할 (8:2)
    import random
    random.shuffle(data)
    split_idx = int(len(data) * 0.8)
    train_data = data[:split_idx]
    val_data = data[split_idx:]
    logger.info(f"Train: {len(train_data)}, Val: {len(val_data)}")

    train_dataset = prepare_dataset(train_data, tokenizer, label2id)
    val_dataset = prepare_dataset(val_data, tokenizer, label2id)

    # 5. 모델 버전 + 출력 디렉토리
    from app.services.model_manager import get_next_version

    version = get_next_version()
    output_dir = Path(settings.ner_model_base_dir) / version
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir} (version: {version})")

    # 6. Training
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=3,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_steps=10,
        max_grad_norm=1.0,
        learning_rate=5e-5,
        weight_decay=0.01,
        warmup_ratio=0.1,
        no_cuda=True,  # CPU 전용 (AMD GPU, CUDA 미지원)
        save_total_limit=2,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=lambda p: compute_metrics(p, id2label),
    )

    logger.info("Starting fine-tuning...")
    trainer.train()

    # 7. 최종 평가
    eval_results = trainer.evaluate()
    f1 = eval_results.get("eval_f1", 0.0)
    precision = eval_results.get("eval_precision", 0.0)
    recall = eval_results.get("eval_recall", 0.0)
    logger.info(f"Evaluation: F1={f1:.4f}, Precision={precision:.4f}, Recall={recall:.4f}")

    # 8. 모델 저장
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    logger.info(f"Model saved to {output_dir}")

    # 9. DB에 모델 버전 기록
    save_model_version(
        version=version,
        model_path=str(output_dir),
        samples_count=len(train_data),
        f1=f1,
        precision=precision,
        recall=recall,
        base_model=base_model,
    )

    # 10. 학습 데이터 사용 완료 표시
    sample_ids = [d["id"] for d in data]
    mark_samples_used(sample_ids)

    # 11. Quality gate 확인 + 자동 승격
    from app.services.model_manager import should_promote, promote_model

    # 현재 active 모델의 F1 조회
    current_f1 = None  # base 모델은 F1 없음
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy import select
        from app.models.ner_training import NerModelVersion

        engine = create_async_engine(settings.database_url, pool_size=2)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _get_active_f1():
            async with factory() as db:
                result = await db.execute(
                    select(NerModelVersion.eval_f1_score).where(
                        NerModelVersion.is_active == True  # noqa: E712
                    )
                )
                row = result.scalar_one_or_none()
                return row

        loop = asyncio.new_event_loop()
        try:
            current_f1 = loop.run_until_complete(_get_active_f1())
        finally:
            loop.run_until_complete(engine.dispose())
            loop.close()
    except Exception:
        pass

    if should_promote(f1, current_f1):
        logger.info(f"Quality gate passed (new={f1:.4f}, current={current_f1}), promoting {version}")
        promote_model(version)

        try:
            from app.services.webhook import send_webhook
            send_webhook(
                title="NER 모델 승격 완료",
                description=(
                    f"버전: {version}\n"
                    f"F1: {f1:.4f} (이전: {current_f1 or 'N/A'})\n"
                    f"학습 데이터: {len(train_data)}건\n"
                    f"워커 재시작 후 적용됩니다."
                ),
                color=0x2ECC71,
            )
        except Exception:
            pass
    else:
        logger.warning(f"Quality gate failed (new={f1:.4f}, current={current_f1}), model saved but NOT promoted")

    return {
        "status": "ok",
        "version": version,
        "f1": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "train_samples": len(train_data),
        "val_samples": len(val_data),
        "promoted": should_promote(f1, current_f1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BERT NER Fine-tuning")
    parser.add_argument("--dry-run", action="store_true", help="데이터 확인만 (학습 미실행)")
    args = parser.parse_args()

    result = run_finetune(dry_run=args.dry_run)
    logger.info(f"Result: {result}")
