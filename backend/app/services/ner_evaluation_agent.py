"""
# ner_evaluation_agent.py - GPT-5 Function Calling NER Evaluation Agent
# Version: 0.1.0
# Description: Azure OpenAI function calling 기반 NER 품질 평가 + 교정 에이전트
# Changes:
#   - 0.1.0: Function calling으로 구조화된 NER 평가/교정 결과 생성
"""

import logging
from dataclasses import dataclass, field

from app.services.azure_openai import call_gpt_with_tools_sync

logger = logging.getLogger(__name__)


@dataclass
class NERCorrectionResult:
    """GPT NER 평가 + 교정 결과"""
    quality_score: float = 0.0
    corrected_entities: list[dict] = field(default_factory=list)
    missed_entities: list[dict] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    reasoning: str = ""
    success: bool = True


# Function calling 스키마
_SUBMIT_NER_EVALUATION_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_ner_evaluation",
        "description": "NER 키워드 추출 품질 평가 결과를 제출합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "quality_score": {
                    "type": "number",
                    "description": "NER 추출 품질 점수 (0.0~1.0). 1.0은 완벽한 추출.",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "corrected_entities": {
                    "type": "array",
                    "description": "올바르게 교정된 전체 엔터티 목록 (누락/오류 수정 포함)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "엔터티 텍스트 (예: '윤석열')",
                            },
                            "type": {
                                "type": "string",
                                "enum": ["PS", "OG", "LC", "DT", "TI", "QT"],
                                "description": "엔터티 유형: PS(인물), OG(기관), LC(장소), DT(날짜), TI(시간), QT(수량)",
                            },
                            "start_char": {
                                "type": "integer",
                                "description": "제목 내 시작 문자 인덱스 (0-based)",
                            },
                            "end_char": {
                                "type": "integer",
                                "description": "제목 내 끝 문자 인덱스 (exclusive)",
                            },
                        },
                        "required": ["text", "type", "start_char", "end_char"],
                    },
                },
                "missed_entities": {
                    "type": "array",
                    "description": "원본 추출에서 누락된 엔터티 목록",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["PS", "OG", "LC", "DT", "TI", "QT"],
                            },
                        },
                        "required": ["text", "type"],
                    },
                },
                "false_positives": {
                    "type": "array",
                    "description": "잘못 추출된 키워드 목록 (실제 엔터티가 아닌 것)",
                    "items": {"type": "string"},
                },
                "reasoning": {
                    "type": "string",
                    "description": "평가 근거 설명 (어떤 엔터티가 누락/오류/올바른지)",
                },
            },
            "required": ["quality_score", "corrected_entities", "reasoning"],
        },
    },
}

_SYSTEM_MESSAGE = (
    "당신은 한국어 뉴스 NER(Named Entity Recognition) 품질 평가 전문가입니다. "
    "주어진 뉴스 제목에서 추출된 키워드/엔터티의 품질을 평가하고, "
    "올바른 엔터티 목록을 교정하여 제출하세요. "
    "특히 한국어 인명의 띄어쓰기에 주의하세요 (예: '윤석열'은 3글자 인명)."
)


def evaluate_and_correct(
    title: str,
    extracted_keywords: dict,
    max_retries: int = 2,
) -> NERCorrectionResult:
    """
    GPT-5 function calling으로 NER 품질 평가 + 교정

    Args:
        title: 뉴스 기사 제목
        extracted_keywords: 추출된 키워드 데이터 {"keywords": [...], "entities": [...], "method": "..."}
        max_retries: 최대 재시도 횟수

    Returns:
        NERCorrectionResult: 구조화된 평가 + 교정 결과
    """
    keywords = extracted_keywords.get("keywords", [])
    entities = extracted_keywords.get("entities", [])
    method = extracted_keywords.get("method", "unknown")

    entities_str = ", ".join(
        f'{e["text"]}({e["type"]})' for e in entities
    ) if entities else "없음"

    prompt = f"""다음 한국 뉴스 기사 제목에서 추출된 NER 결과를 평가하고 교정해주세요.

제목: {title}
추출 방법: {method}
추출된 키워드: {', '.join(keywords) if keywords else '없음'}
추출된 엔터티: {entities_str}

평가 기준:
1. 핵심 인물(PS)/기관(OG)/장소(LC) 등이 올바르게 추출되었는가?
2. 한국어 인명 띄어쓰기 오류 (예: "윤석" → "윤석열")
3. 누락된 중요 엔터티가 있는가?
4. 잘못 추출된 엔터티(false positive)가 있는가?

submit_ner_evaluation 함수를 호출하여 평가 결과를 제출하세요.
corrected_entities에는 제목에서 찾을 수 있는 모든 올바른 엔터티를 포함하세요.
start_char와 end_char는 제목 문자열에서의 정확한 위치여야 합니다."""

    tools = [_SUBMIT_NER_EVALUATION_TOOL]
    tool_choice = {"type": "function", "function": {"name": "submit_ner_evaluation"}}

    for attempt in range(max_retries):
        try:
            result = call_gpt_with_tools_sync(
                prompt=prompt,
                tools=tools,
                system_message=_SYSTEM_MESSAGE,
                max_tokens=4096,
                tool_choice=tool_choice,
            )

            return NERCorrectionResult(
                quality_score=float(result.get("quality_score", 0.0)),
                corrected_entities=result.get("corrected_entities", []),
                missed_entities=result.get("missed_entities", []),
                false_positives=result.get("false_positives", []),
                reasoning=result.get("reasoning", ""),
                success=True,
            )

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"NER evaluation attempt {attempt+1} failed: {e}, retrying...")
                continue
            logger.error(f"NER evaluation failed after {max_retries} retries: {e}")
            return NERCorrectionResult(
                quality_score=-1.0,
                reasoning=f"evaluation failed: {str(e)[:200]}",
                success=False,
            )
