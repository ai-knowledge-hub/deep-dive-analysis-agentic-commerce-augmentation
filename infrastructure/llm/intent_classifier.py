from __future__ import annotations

from typing import Any, Dict

from modules.intent.llm_classifier import HybridIntentClassifier


def classify_intent(query: str) -> Dict[str, Any]:
    """Thin wrapper around the current intent classifier."""
    return HybridIntentClassifier().classify(query).to_dict()


__all__ = ["classify_intent"]

