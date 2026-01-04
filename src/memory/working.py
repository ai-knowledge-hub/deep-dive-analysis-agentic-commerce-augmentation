"""In-session memory used to keep track of the immediate conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Turn:
    speaker: str
    text: str


class WorkingMemory:
    def __init__(self) -> None:
        self._events: List[Turn] = []

    def add(self, speaker: str, text: str) -> None:
        self._events.append(Turn(speaker=speaker, text=text))

    def last(self, count: int = 5) -> List[Turn]:
        return self._events[-count:]

    def summarize(self) -> str:
        return "\n".join(f"{turn.speaker}: {turn.text}" for turn in self._events[-8:])
