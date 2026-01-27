"""Infrastructure loader for the intent taxonomy JSON file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from domain.intent.types import IntentDefinition

_DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "intent_taxonomy.json"
)


def load_intent_taxonomy(path: Path | None = None) -> List[IntentDefinition]:
    intent_path = path or _DEFAULT_TAXONOMY_PATH
    with intent_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [IntentDefinition(**item) for item in payload]


INTENT_TAXONOMY: List[IntentDefinition] = load_intent_taxonomy()

__all__ = ["INTENT_TAXONOMY", "load_intent_taxonomy"]
