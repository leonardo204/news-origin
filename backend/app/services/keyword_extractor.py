"""
# keyword_extractor.py - BERT NER 기반 키워드 추출 서비스
# Version: 0.1.0
# Description: klue/bert-base NER 모델로 뉴스 제목에서 엔터티/키워드 추출
# Changes:
#   - 0.1.0: NER 모델 싱글톤 로딩, 엔터티 추출, kiwipiepy 폴백
"""

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_extractor: Optional["KeywordExtractor"] = None


# NER 엔터티 유형별 가중치 (클러스터링 스코어링에 사용)
ENTITY_WEIGHTS = {
    "PS": 3.0,   # 인물 - 가장 차별적
    "OG": 2.0,   # 기관/단체
    "LC": 1.0,   # 장소
    "DT": 0.5,   # 날짜
    "TI": 0.3,   # 시간
    "QT": 0.3,   # 수량
    "NOUN": 1.5, # 일반 명사 (kiwipiepy 폴백)
}


class KeywordExtractor:
    """
    뉴스 제목에서 키워드/엔터티 추출

    [BUSINESS LOGIC]
    1순위: BERT NER 모델 (fine-tuned 경로가 있으면 사용)
    2순위: kiwipiepy 형태소 분석 (NER 모델 없을 때 폴백)

    추출 결과 형식:
    {
        "keywords": ["윤미라", "호텔", "조식권"],
        "entities": [
            {"text": "윤미라", "type": "PS", "weight": 3.0},
            {"text": "호텔", "type": "NOUN", "weight": 1.5},
        ],
        "method": "bert_ner" | "kiwipiepy"
    }
    """

    def __init__(self):
        self._ner_pipeline = None
        self._kiwi = None
        self._use_bert_ner = False
        self._loaded = False

    def _load(self):
        """모델 로딩 (최초 1회)"""
        if self._loaded:
            return

        model_path = settings.bert_ner_model_path or settings.bert_model_name

        # BERT NER 모델 로딩 시도
        try:
            from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForTokenClassification.from_pretrained(model_path)

            # NER head가 있는지 확인 (label 수가 2 이상)
            num_labels = model.config.num_labels
            if num_labels > 2:
                self._ner_pipeline = pipeline(
                    "ner",
                    model=model,
                    tokenizer=tokenizer,
                    aggregation_strategy="simple",
                    device=-1,  # CPU 전용
                )
                self._use_bert_ner = True
                logger.info(f"BERT NER model loaded: {model_path} ({num_labels} labels)")
            else:
                logger.warning(
                    f"Model {model_path} has only {num_labels} labels, "
                    "falling back to kiwipiepy"
                )
                self._load_kiwi()
        except Exception as e:
            logger.warning(f"BERT NER model load failed ({e}), falling back to kiwipiepy")
            self._load_kiwi()

        self._loaded = True

    def _load_kiwi(self):
        """kiwipiepy 형태소 분석기 로딩"""
        from kiwipiepy import Kiwi
        self._kiwi = Kiwi()
        self._use_bert_ner = False
        logger.info("kiwipiepy morphological analyzer loaded as fallback")

    @staticmethod
    def _strip_publisher_suffix(title: str) -> str:
        """제목 끝의 ' - 언론사명' 패턴 제거

        Google News RSS 제목에 포함된 언론사명이 키워드로 추출되는 것을 방지.
        예: "기사 제목 - 매일경제" → "기사 제목"
        """
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            suffix = parts[-1].strip()
            # 언론사명은 보통 2~15자, 특수문자 없음
            if 2 <= len(suffix) <= 15 and not any(c in suffix for c in ".,!?;:()[]{}"):
                return parts[0].strip()
        return title

    def extract(self, title: str) -> dict:
        """
        단일 제목에서 키워드 추출

        Returns: {"keywords": [...], "entities": [...], "method": "..."}
        """
        self._load()
        title = self._strip_publisher_suffix(title)

        if self._use_bert_ner:
            return self._extract_with_bert(title)
        return self._extract_with_kiwi(title)

    def extract_batch(self, titles: list[str]) -> list[dict]:
        """
        배치 제목에서 키워드 추출

        [CRITICAL] 대량 기사 처리 시 사용
        """
        self._load()
        titles = [self._strip_publisher_suffix(t) for t in titles]

        if self._use_bert_ner:
            return [self._extract_with_bert(t) for t in titles]
        return [self._extract_with_kiwi(t) for t in titles]

    def _extract_with_bert(self, title: str) -> dict:
        """BERT NER 기반 엔터티 추출"""
        results = self._ner_pipeline(title)

        entities = []
        keywords = []
        seen = set()

        for ent in results:
            text = ent["word"].strip()
            if not text or len(text) < 2 or text in seen:
                continue

            # KLUE-NER label format: B-PS, I-PS 등 → PS 추출
            label = ent.get("entity_group", ent.get("entity", ""))
            entity_type = label.replace("B-", "").replace("I-", "")

            weight = ENTITY_WEIGHTS.get(entity_type, 1.0)

            # 신뢰도 낮은 엔터티 필터링
            if ent.get("score", 0) < 0.5:
                continue

            seen.add(text)
            keywords.append(text)
            entities.append({
                "text": text,
                "type": entity_type,
                "weight": weight,
                "score": round(ent.get("score", 0), 3),
            })

        return {
            "keywords": keywords,
            "entities": entities,
            "method": "bert_ner",
        }

    def _extract_with_kiwi(self, title: str) -> dict:
        """kiwipiepy 형태소 분석 기반 키워드 추출"""
        tokens = self._kiwi.tokenize(title)

        entities = []
        keywords = []
        seen = set()

        # 불용어 (조사, 어미, 접미사 등 제외)
        stop_tags = {"JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ", "JX", "JC",
                     "EP", "EF", "EC", "ETN", "ETM", "SF", "SP", "SS", "SE", "SO",
                     "SW", "SH"}

        for token in tokens:
            text = token.form.strip()
            tag = token.tag

            if not text or len(text) < 2 or text in seen:
                continue
            if tag in stop_tags:
                continue

            # 고유명사 (NNP) → 인물/기관/장소 가능성 높음
            if tag == "NNP":
                entity_type = "PS"  # 고유명사 기본 타입
                weight = ENTITY_WEIGHTS["PS"]
            elif tag == "NNG":
                entity_type = "NOUN"
                weight = ENTITY_WEIGHTS["NOUN"]
            elif tag == "SL":  # 외국어
                entity_type = "NOUN"
                weight = ENTITY_WEIGHTS["NOUN"]
            elif tag in ("NR", "SN"):  # 수사/숫자
                entity_type = "QT"
                weight = ENTITY_WEIGHTS["QT"]
            else:
                continue

            seen.add(text)
            keywords.append(text)
            entities.append({
                "text": text,
                "type": entity_type,
                "weight": weight,
                "score": 1.0,  # 형태소 분석은 신뢰도 고정
            })

        return {
            "keywords": keywords,
            "entities": entities,
            "method": "kiwipiepy",
        }


def get_extractor() -> KeywordExtractor:
    """키워드 추출기 싱글톤"""
    global _extractor
    if _extractor is None:
        _extractor = KeywordExtractor()
    return _extractor


def extract_keywords(title: str) -> dict:
    """단일 제목에서 키워드 추출 (편의 함수)"""
    return get_extractor().extract(title)


def extract_keywords_batch(titles: list[str]) -> list[dict]:
    """배치 제목에서 키워드 추출 (편의 함수)"""
    return get_extractor().extract_batch(titles)


def compute_keyword_similarity(keywords_a: dict, keywords_b: dict) -> float:
    """
    두 기사의 키워드 유사도 계산

    [BUSINESS LOGIC]
    엔터티 유형별 가중치를 적용한 겹침 점수 계산
    - 동일 인물(PS)이 겹치면 높은 점수
    - 동일 기관(OG)이 겹치면 중간 점수
    - 일반 명사(NOUN)만 겹치면 낮은 점수
    """
    entities_a = {(e["text"], e["type"]): e["weight"] for e in keywords_a.get("entities", [])}
    entities_b = {(e["text"], e["type"]): e["weight"] for e in keywords_b.get("entities", [])}

    if not entities_a or not entities_b:
        return 0.0

    # 겹치는 엔터티의 가중치 합산
    common_keys = set(entities_a.keys()) & set(entities_b.keys())
    if not common_keys:
        # 텍스트만 비교 (유형 무관)
        texts_a = {k[0] for k in entities_a.keys()}
        texts_b = {k[0] for k in entities_b.keys()}
        common_texts = texts_a & texts_b
        if not common_texts:
            return 0.0
        # 텍스트 겹침에 대한 가중치 (유형 불일치 페널티)
        weighted_sum = sum(
            min(
                max((w for (t, _), w in entities_a.items() if t == text), default=1.0),
                max((w for (t, _), w in entities_b.items() if t == text), default=1.0),
            ) * 0.7  # 유형 불일치 페널티
            for text in common_texts
        )
    else:
        weighted_sum = sum(
            max(entities_a[k], entities_b[k])
            for k in common_keys
        )

    # 최대 가능 가중치 합산으로 정규화
    max_possible = max(
        sum(entities_a.values()),
        sum(entities_b.values()),
    )

    if max_possible == 0:
        return 0.0

    return min(weighted_sum / max_possible, 1.0)
