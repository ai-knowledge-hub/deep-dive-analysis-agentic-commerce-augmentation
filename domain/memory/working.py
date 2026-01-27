"""Pure in-session working memory."""

from __future__ import annotations

from typing import List

from domain.memory.types import Turn


class WorkingMemory:
    """In-memory working memory for a single conversation session."""

    def __init__(self) -> None:
        self._events: List[Turn] = []

    def add(self, speaker: str, text: str) -> None:
        self._events.append(Turn(speaker=speaker, text=text))

    def last(self, count: int = 5) -> List[Turn]:
        return self._events[-count:]

    def summarize(self) -> str:
        return "\n".join(f"{turn.speaker}: {turn.text}" for turn in self._events[-8:])


__all__ = ["WorkingMemory"]
