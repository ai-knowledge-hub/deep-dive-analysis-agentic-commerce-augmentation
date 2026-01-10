"""Backward compatibility: re-exports from modules.intent.llm_classifier."""

from modules.intent.domain import Intent as IntentResult
from modules.intent.llm_classifier import HybridIntentClassifier

__all__ = ["IntentResult", "HybridIntentClassifier"]
