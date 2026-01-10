"""Intent module - intent classification and taxonomy management.

This module owns all intent detection, classification, and taxonomy definitions.
"""

from modules.intent.domain import Intent, IntentDefinition, IntentContext
from modules.intent.taxonomy import INTENT_TAXONOMY, iter_keywords, load_intent_taxonomy
from modules.intent.classifier import classify, KeywordClassifier
from modules.intent.llm_classifier import HybridIntentClassifier

__all__ = [
    "Intent",
    "IntentDefinition",
    "IntentContext",
    "INTENT_TAXONOMY",
    "iter_keywords",
    "load_intent_taxonomy",
    "classify",
    "KeywordClassifier",
    "HybridIntentClassifier",
]
