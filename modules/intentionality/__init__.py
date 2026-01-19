"""Intentionality module - product profiling for intent legibility."""

from modules.intentionality.domain import IntentionalityProfile
from modules.intentionality.profiling import build_profile

__all__ = ["IntentionalityProfile", "build_profile"]
