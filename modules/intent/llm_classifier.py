"""Compatibility shim for Hybrid intent inference (LLM + keyword fallback).

Canonical orchestration lives in `infrastructure.llm.hybrid_intent_classifier`.
This module preserves test monkeypatch seams:
- `modules.intent.llm_classifier.generate`
- `modules.intent.llm_classifier.keyword_classifier.classify`
"""

from __future__ import annotations

from shared.llm.gateway import generate
from shared.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from modules.intent import classifier as keyword_classifier
from infrastructure.llm.hybrid_intent_classifier import (
    HybridIntentClassifier as _HybridIntentClassifier,
)


class HybridIntentClassifier:
    def __init__(self, threshold: float = 0.55) -> None:
        self._impl = _HybridIntentClassifier(
            threshold=threshold,
            generate_fn=generate,
            keyword_classify_fn=keyword_classifier.classify,
            prompt_template=INTENT_CLASSIFICATION_PROMPT,
        )

    def classify(self, text: str, context: str | None = None):
        return self._impl.classify(text, context=context)


__all__ = ["HybridIntentClassifier"]
