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
        keyword_intent = keyword_classifier.classify(
            text,
            llm_fallback=self._call_llm,
            llm_threshold=self.threshold,
        )
        return IntentResult(
            label=keyword_intent.label,
            confidence=keyword_intent.confidence,
            evidence=keyword_intent.evidence,
            domain=keyword_intent.domain,
            clarifying_questions=keyword_intent.clarifying_questions,
            source=keyword_intent.source,
        )

    # Core helpers -----------------------------------------------------
    def _call_llm(self, text: str) -> Dict[str, object]:
        try:
            raw = generate(prompt=f"{INTENT_CLASSIFICATION_PROMPT}\nInput: {text}")
            parsed = self._parse_raw_response(raw)
        except Exception:
            parsed = {}

        parsed["source"] = parsed.get("source", "gemini")
        return parsed

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
