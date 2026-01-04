"""Long-lived semantic memory backed by a JSON document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


class SemanticMemory:
    def __init__(self, data_path: Path | None = None) -> None:
        self._path = data_path or Path(__file__).resolve().parents[2] / "data" / "demo_memory.json"
        self._store: Dict[str, List[str]] = self._load()

    def get(self, key: str) -> List[str]:
        return self._store.get(key, [])

    def set(self, key: str, values: List[str]) -> None:
        self._store[key] = values
        self._persist()

    def append(self, key: str, value: str) -> None:
        self._store.setdefault(key, []).append(value)
        self._persist()

    def _load(self) -> Dict[str, List[str]]:
        if not self._path.exists():
            return {"goals": [], "capabilities": [], "episodes": []}
        with self._path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return {key: value for key, value in data.items() if isinstance(value, list)}

    def _persist(self) -> None:
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(self._store, handle, indent=2)
