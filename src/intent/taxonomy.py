"""Simplified intent taxonomy mirroring CCO categories."""

from __future__ import annotations

from typing import Iterable, List

from core.schema.intent import IntentDefinition, iter_keywords as _iter_keywords, load_intent_taxonomy

INTENT_TAXONOMY: List[IntentDefinition] = load_intent_taxonomy()


def iter_keywords() -> Iterable[str]:
    yield from _iter_keywords(INTENT_TAXONOMY)
