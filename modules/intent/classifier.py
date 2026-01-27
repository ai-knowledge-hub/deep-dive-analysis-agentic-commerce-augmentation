"""Compatibility shim for keyword-based intent inference.

Canonical implementation lives in `domain.intent.keyword_classifier`.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from domain.intent.keyword_classifier import KeywordClassifier as _KeywordClassifier
from domain.intent.keyword_classifier import classify as _classify
from modules.intent.taxonomy import INTENT_TAXONOMY


LLMClassifier = Callable[[str], Mapping[str, Any]]


def classify(
    user_text: str,
    llm_fallback: LLMClassifier | None = None,
    llm_threshold: float = 0.55,
):
    return _classify(
        user_text,
        taxonomy=INTENT_TAXONOMY,
        llm_fallback=llm_fallback,
        llm_threshold=llm_threshold,
    )


class KeywordClassifier(_KeywordClassifier):
    def __init__(self, taxonomy=None) -> None:  # type: ignore[override]
        super().__init__(taxonomy or INTENT_TAXONOMY)


__all__ = ["classify", "KeywordClassifier", "LLMClassifier"]
