"""Post-action reflection memory capturing lessons."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Episode:
    timestamp: datetime
    outcome: str
    takeaways: List[str]


class EpisodicMemory:
    def __init__(self) -> None:
        self._episodes: List[Episode] = []

    def record(self, outcome: str, takeaways: List[str]) -> Episode:
        episode = Episode(timestamp=datetime.utcnow(), outcome=outcome, takeaways=takeaways)
        self._episodes.append(episode)
        return episode

    def latest(self) -> Episode | None:
        return self._episodes[-1] if self._episodes else None
