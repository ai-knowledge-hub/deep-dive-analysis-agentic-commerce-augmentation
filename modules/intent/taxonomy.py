"""Intent taxonomy loading and management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from modules.intent.domain import IntentDefinition


_DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "intent_taxonomy.json"
)


def load_intent_taxonomy(path: Path | None = None) -> List[IntentDefinition]:
    """Load intent definitions from JSON taxonomy file."""
    intent_path = path or _DEFAULT_TAXONOMY_PATH
    with intent_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [IntentDefinition(**item) for item in payload]


def iter_keywords(
    definitions: Iterable[IntentDefinition] | None = None,
) -> Iterable[str]:
    """Iterate over all keywords from intent definitions."""
    defs = definitions if definitions is not None else INTENT_TAXONOMY
    for definition in defs:
        yield from definition.keywords


# Load taxonomy at module import time
INTENT_TAXONOMY: List[IntentDefinition] = load_intent_taxonomy()


__all__ = [
    "INTENT_TAXONOMY",
    "iter_keywords",
    "load_intent_taxonomy",
    "IntentDefinition",
]
