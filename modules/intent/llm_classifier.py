"""Hybrid intent classifier combining LLM with keyword fallback."""

from __future__ import annotations

import json
from typing import Dict, List

from shared.llm.gateway import generate
from shared.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from modules.intent.domain import Intent
from modules.intent import classifier as keyword_classifier


class HybridIntentClassifier:
    """Intent classifier that uses LLM first with keyword fallback."""

    def __init__(self, threshold: float = 0.55) -> None:
        self.threshold = threshold
        self._context: str | None = None

    def classify(self, text: str, context: str | None = None) -> Intent:
        """Classify intent using LLM with keyword fallback.

        Args:
            text: User input text to classify
            context: Optional session context for better classification

        Returns:
            Intent object with classification result
        """
        previous_context = self._context
        self._context = context

        keyword_intent = keyword_classifier.classify(
            text,
            llm_fallback=self._call_llm,
            llm_threshold=self.threshold,
        )

        self._context = previous_context
        return keyword_intent

    def _call_llm(self, text: str) -> Dict[str, object]:
        """Call LLM for intent classification."""
        try:
            context = f"\n\nSession context:\n{self._context}" if self._context else ""
            raw = generate(prompt=f"{INTENT_CLASSIFICATION_PROMPT}{context}\nInput: {text}")
            parsed = self._parse_raw_response(raw)
        except Exception:
            parsed = {}

        parsed["source"] = parsed.get("source", "gemini")
        return parsed

    def _parse_raw_response(self, response: str) -> Dict[str, object]:
        """Parse JSON response from LLM."""
        if not response:
            return {}
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _get_str(self, data: Dict[str, object], key: str, default: str) -> str:
        """Extract string value from dict."""
        value = data.get(key, default)
        return value if isinstance(value, str) else default

    def _get_list(self, data: Dict[str, object], key: str, default: List[str]) -> List[str]:
        """Extract list value from dict."""
        value = data.get(key, default)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
        return default

    def _get_float(self, data: Dict[str, object], key: str, default: float) -> float:
        """Extract float value from dict."""
        value = data.get(key, default)
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default


__all__ = ["HybridIntentClassifier"]
