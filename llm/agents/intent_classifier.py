"""Hybrid intent classifier (Gemini-first with keyword resilience)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

from llm.gateway import generate
from llm.prompts import INTENT_CLASSIFICATION_PROMPT
from src.intent import classifier as keyword_classifier


@dataclass
class IntentResult:
    label: str
    confidence: float
    evidence: List[str]
    domain: str
    clarifying_questions: List[str]
    source: str = "gemini"

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "domain": self.domain,
            "clarifying_questions": self.clarifying_questions,
            "source": self.source,
        }


class HybridIntentClassifier:
    def __init__(self, threshold: float = 0.55) -> None:
        self.threshold = threshold

    def classify(self, text: str) -> IntentResult:
        keyword_result = keyword_classifier.classify(text)
        llm_intent = self._call_llm(text, keyword_result)

        if self._should_fallback(llm_intent):
            return self._merge_with_keyword(llm_intent, keyword_result)
        return llm_intent

    # Core helpers -----------------------------------------------------
    def _call_llm(self, text: str, keyword_result) -> IntentResult:
        try:
            raw = generate(prompt=f"{INTENT_CLASSIFICATION_PROMPT}\nInput: {text}")
            parsed = self._parse_raw_response(raw)
        except Exception:
            parsed = {}

        return IntentResult(
            label=self._get_str(parsed, "intent", keyword_result.label),
            confidence=self._get_float(parsed, "confidence", keyword_result.confidence),
            evidence=self._get_list(parsed, "evidence", keyword_result.evidence),
            domain=self._get_str(parsed, "domain", keyword_result.domain),
            clarifying_questions=self._get_list(
                parsed, "clarifying_questions", keyword_result.clarifying_questions
            ),
            source="gemini",
        )

    def _should_fallback(self, intent: IntentResult) -> bool:
        return intent.confidence < self.threshold or intent.label in {"", "unknown"}

    def _merge_with_keyword(self, llm_intent: IntentResult, keyword_result) -> IntentResult:
        data = keyword_result.to_dict()
        return IntentResult(
            label=str(data.get("label", llm_intent.label)),
            confidence=max(
                float(data.get("confidence", 0.0)),
                llm_intent.confidence,
            ),
            evidence=llm_intent.evidence or list(data.get("evidence", [])),
            domain=str(data.get("domain", llm_intent.domain)),
            clarifying_questions=llm_intent.clarifying_questions
            or list(data.get("clarifying_questions", [])),
            source="keyword_fallback",
        )

    # Parsing utilities ------------------------------------------------
    def _parse_raw_response(self, response: str) -> Dict[str, object]:
        if not response:
            return {}
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _get_str(self, data: Dict[str, object], key: str, default: str) -> str:
        value = data.get(key, default)
        return value if isinstance(value, str) else default

    def _get_list(self, data: Dict[str, object], key: str, default: List[str]) -> List[str]:
        value = data.get(key, default)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
        return default

    def _get_float(self, data: Dict[str, object], key: str, default: float) -> float:
        value = data.get(key, default)
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
