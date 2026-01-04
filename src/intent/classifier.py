"""Lightweight intent classifier that mimics the CCIA surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .taxonomy import INTENT_TAXONOMY


@dataclass
class Intent:
    label: str
    confidence: float
    evidence: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


def classify(user_text: str) -> Intent:
    """Return an intent by naive keyword matching against the taxonomy."""

    user_text_lower = user_text.lower()
    for intent_label, keywords in INTENT_TAXONOMY.items():
        if any(keyword in user_text_lower for keyword in keywords):
            return Intent(label=intent_label, confidence=0.72, evidence=keywords[:2])
    return Intent(label="unknown", confidence=0.1, evidence=["insufficient context"])
