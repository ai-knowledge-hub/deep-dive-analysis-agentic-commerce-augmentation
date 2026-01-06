"""Hybrid intent classifier (keywords + LLM fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from src.intent import classifier as keyword_classifier
from llm.gateway import generate
from llm.prompts import INTENT_CLASSIFICATION_PROMPT


@dataclass
class IntentResult:
    label: str
    confidence: float
    evidence: List[str]
    domain: str
    clarifying_questions: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "domain": self.domain,
            "clarifying_questions": self.clarifying_questions,
        }


class HybridIntentClassifier:
    threshold: float = 0.8

    def classify(self, text: str) -> IntentResult:
        keyword_result = keyword_classifier.classify(text)
        if keyword_result.confidence >= self.threshold:
            data = keyword_result.to_dict()
            return IntentResult(
                label=str(data.get("label", "")),
                confidence=float(data.get("confidence", 0.0)),
                evidence=list(data.get("evidence", [])),
                domain=str(data.get("domain", "")),
                clarifying_questions=list(data.get("clarifying_questions", [])),
            )

        llm_response = generate(
            prompt=f"{INTENT_CLASSIFICATION_PROMPT}\nInput: {text}",
        )
        parsed = self._parse_llm_response(llm_response)
        return IntentResult(
            label=self._get_str(parsed, "intent", keyword_result.label),
            confidence=self._get_float(parsed, "confidence", keyword_result.confidence),
            evidence=self._get_list(parsed, "evidence", keyword_result.evidence),
            domain=self._get_str(parsed, "domain", keyword_result.domain),
            clarifying_questions=self._get_list(
                parsed, "clarifying_questions", keyword_result.clarifying_questions
            ),
        )

    def _parse_llm_response(self, response: str) -> Dict[str, List[str] | str | float]:
        try:
            import json
            return json.loads(response)
        except Exception:
            return {}

    def _get_str(self, data: dict, key: str, default: str) -> str:
        value = data.get(key, default)
        return value if isinstance(value, str) else default

    def _get_list(self, data: dict, key: str, default: List[str]) -> List[str]:
        value = data.get(key, default)
        return value if isinstance(value, list) else default

    def _get_float(self, data: dict, key: str, default: float) -> float:
        value = data.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
