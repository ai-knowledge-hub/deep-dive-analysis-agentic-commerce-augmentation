"""Infrastructure Hybrid intent classifier (LLM + keyword fallback).

This lives in infrastructure because it coordinates an LLM call and parsing.
Keyword scoring lives in `domain/intent/keyword_classifier.py`.
"""

from __future__ import annotations

import json
from typing import Callable, Dict

from domain.intent.types import InferredIntent


GenerateFn = Callable[..., str]
KeywordClassifyFn = Callable[..., InferredIntent]


class HybridIntentClassifier:
    """Intent inference that uses LLM first with keyword fallback."""

    def __init__(
        self,
        *,
        threshold: float = 0.55,
        generate_fn: GenerateFn,
        keyword_classify_fn: KeywordClassifyFn,
        prompt_template: str,
    ) -> None:
        self.threshold = threshold
        self._generate_fn = generate_fn
        self._keyword_classify_fn = keyword_classify_fn
        self._prompt_template = prompt_template
        self._context: str | None = None

    def classify(self, text: str, *, context: str | None = None) -> InferredIntent:
        previous_context = self._context
        self._context = context
        try:
            return self._keyword_classify_fn(
                text,
                llm_fallback=self._call_llm,
                llm_threshold=self.threshold,
            )
        finally:
            self._context = previous_context

    def _call_llm(self, text: str) -> Dict[str, object]:
        try:
            context = f"\n\nSession context:\n{self._context}" if self._context else ""
            raw = self._generate_fn(
                prompt=f"{self._prompt_template}{context}\nInput: {text}"
            )
            parsed = self._parse_raw_response(raw)
        except Exception:
            parsed = {}

        parsed["source"] = parsed.get("source", "gemini")
        return parsed

    def _parse_raw_response(self, response: str) -> Dict[str, object]:
        if not response:
            return {}
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}


__all__ = ["HybridIntentClassifier", "GenerateFn", "KeywordClassifyFn"]

