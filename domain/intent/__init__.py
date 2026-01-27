"""Intent domain logic (pure)."""

from domain.intent.goals import extract_intent_goals
from domain.intent.types import InferredIntent, IntentContext, IntentDefinition

__all__ = [
    "InferredIntent",
    "IntentContext",
    "IntentDefinition",
    "extract_intent_goals",
]
