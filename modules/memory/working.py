"""In-session memory used to keep track of the immediate conversation."""

from __future__ import annotations

from typing import List

from modules.memory.domain import Turn


class WorkingMemory:
    """In-memory working memory for a single conversation session."""

    def __init__(self) -> None:
        self._events: List[Turn] = []

    def add(self, speaker: str, text: str) -> None:
        """Add a conversation turn."""
        self._events.append(Turn(speaker=speaker, text=text))

    def last(self, count: int = 5) -> List[Turn]:
        """Get the last N turns."""
        return self._events[-count:]

    def summarize(self) -> str:
        """Create a text summary of recent turns."""
        return "\n".join(f"{turn.speaker}: {turn.text}" for turn in self._events[-8:])


__all__ = ["WorkingMemory"]
