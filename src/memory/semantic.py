"""Long-lived semantic memory (mocked goals/capabilities)."""

from __future__ import annotations

from typing import Dict, List


class SemanticMemory:
    def __init__(self) -> None:
        self._store: Dict[str, List[str]] = {
            "goals": ["Improve ergonomics", "Reduce burnout"],
            "capabilities": ["Laptop research", "Budget analysis"],
        }

    def get(self, key: str) -> List[str]:
        return self._store.get(key, [])

    def set(self, key: str, values: List[str]) -> None:
        self._store[key] = values
