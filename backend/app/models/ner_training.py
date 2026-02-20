"""
# ner_training.py - NER MLOps Training Data Models
# Version: 0.1.0
# Description: NER 학습 데이터 수집 + 모델 버전 관리 ORM 모델
# Changes:
#   - 0.1.0: NerTrainingSample, NerModelVersion 테이블
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class NerTrainingSample(Base):
    """GPT 평가 기반 NER 학습 데이터 샘플"""
    __tablename__ = "ner_training_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    title = Column(Text, nullable=False)
    bio_tags = Column(JSONB, nullable=False)  # [["윤","B-PS"],["석","I-PS"],...]
    gpt_quality_score = Column(Float, nullable=False)
    gpt_corrected_entities = Column(JSONB, nullable=False)  # [{text,type,start_char,end_char}]
    gpt_reasoning = Column(Text, nullable=True)
    extraction_model_version = Column(String(20), nullable=True)
    extraction_method = Column(String(20), nullable=True)  # bert_ner | kiwipiepy
    is_used_for_training = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NerModelVersion(Base):
    """BERT NER 모델 버전 관리"""
    __tablename__ = "ner_model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String(20), unique=True, nullable=False)  # v0001, v0002
    base_model = Column(String(100), nullable=True)
    model_path = Column(Text, nullable=True)
    training_samples_count = Column(Integer, nullable=True)
    eval_f1_score = Column(Float, nullable=True)
    eval_precision = Column(Float, nullable=True)
    eval_recall = Column(Float, nullable=True)
    status = Column(String(20), default="training", nullable=False)  # training|ready|active|retired
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
