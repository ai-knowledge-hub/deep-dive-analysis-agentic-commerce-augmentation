"""Canonical intent taxonomy models and loader helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List
import json


@dataclass(frozen=True)
class IntentDefinition:
    label: str
    domain: str
    keywords: List[str]
    questions: List[str]


_DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "data" / "intent_taxonomy.json"


def load_intent_taxonomy(path: Path | None = None) -> List[IntentDefinition]:
    intent_path = path or _DEFAULT_TAXONOMY_PATH
    with intent_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [IntentDefinition(**item) for item in payload]


def iter_keywords(definitions: Iterable[IntentDefinition]) -> Iterable[str]:
    for definition in definitions:
        yield from definition.keywords


__all__ = ["IntentDefinition", "load_intent_taxonomy", "iter_keywords"]
