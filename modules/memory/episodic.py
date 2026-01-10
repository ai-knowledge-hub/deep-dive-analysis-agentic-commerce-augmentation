"""Post-action reflection memory capturing lessons."""

from __future__ import annotations

from datetime import datetime
from typing import List

from modules.memory.domain import Episode


class EpisodicMemory:
    """In-memory episodic memory for capturing outcomes and takeaways."""

    def __init__(self) -> None:
        self._episodes: List[Episode] = []

    def record(self, outcome: str, takeaways: List[str]) -> Episode:
        """Record an episode with outcome and takeaways."""
        episode = Episode(
            timestamp=datetime.utcnow(), outcome=outcome, takeaways=takeaways
        )
        self._episodes.append(episode)
        return episode

    def latest(self) -> Episode | None:
        """Get the latest episode."""
        return self._episodes[-1] if self._episodes else None


__all__ = ["EpisodicMemory"]
