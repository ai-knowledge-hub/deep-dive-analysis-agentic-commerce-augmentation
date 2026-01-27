"""Compatibility shim for intent domain models.

Canonical types now live in `domain.intent.types`.
"""

from __future__ import annotations

from domain.intent.types import InferredIntent, IntentContext, IntentDefinition

__all__ = ["InferredIntent", "IntentContext", "IntentDefinition"]
