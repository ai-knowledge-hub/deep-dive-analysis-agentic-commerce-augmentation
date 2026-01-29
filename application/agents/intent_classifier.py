"""Backward compatibility: intent inference primitives."""

from domain.intent.types import InferredIntent as IntentResult
from infrastructure.llm.hybrid_intent_classifier import HybridIntentClassifier

__all__ = ["IntentResult", "HybridIntentClassifier"]
