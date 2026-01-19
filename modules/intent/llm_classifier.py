"""Hybrid intent inference combining LLM with keyword fallback."""

from __future__ import annotations

import json
from typing import Dict

from shared.llm.gateway import generate
from shared.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from modules.intent.domain import InferredIntent
from modules.intent import classifier as keyword_classifier


class HybridIntentClassifier:
    """Intent inference that uses LLM first with keyword fallback."""

    def __init__(self, threshold: float = 0.55) -> None:
        self.threshold = threshold
        self._context: str | None = None

    def classify(self, text: str, context: str | None = None) -> InferredIntent:
        """Infer intent using LLM with keyword fallback.

        Args:
            text: User input text to classify
            context: Optional session context for better classification

        Returns:
            InferredIntent object with structured intent result
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
        """Call LLM for intent inference."""
        try:
            context = f"\n\nSession context:\n{self._context}" if self._context else ""
            raw = generate(
                prompt=f"{INTENT_CLASSIFICATION_PROMPT}{context}\nInput: {text}"
            )
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


__all__ = ["HybridIntentClassifier"]
