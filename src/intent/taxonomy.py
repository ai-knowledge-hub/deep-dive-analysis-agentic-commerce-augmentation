"""Simplified intent taxonomy mirroring CCO categories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import json

_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "data" / "intent_taxonomy.json"


@dataclass(frozen=True)
class IntentDefinition:
    label: str
    domain: str
    keywords: List[str]
    questions: List[str]


def _load_taxonomy(path: Path = _TAXONOMY_PATH) -> List[IntentDefinition]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [IntentDefinition(**item) for item in payload]


INTENT_TAXONOMY: List[IntentDefinition] = _load_taxonomy()


def iter_keywords() -> Iterable[str]:
    for definition in INTENT_TAXONOMY:
        yield from definition.keywords
