"""In-session memory used to keep track of the immediate conversation."""

from __future__ import annotations

from typing import List


class WorkingMemory:
    def __init__(self) -> None:
        self._events: List[str] = []

    def add(self, event: str) -> None:
        self._events.append(event)

    def last(self, count: int = 5) -> List[str]:
        return self._events[-count:]
