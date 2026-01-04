"""Lightweight intent classifier that mimics the CCIA surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .taxonomy import INTENT_TAXONOMY, IntentDefinition


@dataclass
class Intent:
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


def _score_definition(user_text: str, definition: IntentDefinition) -> Tuple[float, List[str]]:
    hits = [keyword for keyword in definition.keywords if keyword in user_text]
    if not hits:
        return 0.0, []
    coverage = len(hits) / len(definition.keywords)
    salience = max(user_text.count(keyword) for keyword in hits)
    confidence = min(1.0, 0.4 + 0.5 * coverage + 0.1 * salience)
    return confidence, hits


def classify(user_text: str) -> Intent:
    """Return an intent by naive keyword matching against the taxonomy."""

    user_text_lower = user_text.lower()
    ranked = [
        (definition, *_score_definition(user_text_lower, definition))  # type: ignore[misc]
        for definition in INTENT_TAXONOMY
    ]
    ranked = [entry for entry in ranked if entry[1] > 0]
    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        top_definition, confidence, evidence = ranked[0]
        return Intent(
            label=top_definition.label,
            confidence=confidence,
            evidence=evidence,
            domain=top_definition.domain,
            clarifying_questions=top_definition.questions,
        )
    return Intent(
        label="unknown",
        confidence=0.1,
        evidence=["insufficient context"],
        domain="unknown",
        clarifying_questions=["What goal are you working toward?", "How can we help?"],
    )
