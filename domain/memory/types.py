"""Pure memory domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class Turn:
    speaker: str
    text: str


@dataclass
class Episode:
    timestamp: datetime
    outcome: str
    takeaways: List[str]


@dataclass
class Goal:
    id: str
    user_id: str
    goal_text: str
    session_id: str | None = None
    domain: str | None = None
    importance: float = 0.5
    created_at: str | None = None


@dataclass
class SessionSnapshot:
    session: Dict[str, Any]
    turns: List[Dict[str, Any]] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    semantic_goals: List[str] = field(default_factory=list)
    latest_episode: Dict[str, Any] | None = None


__all__ = ["Turn", "Episode", "Goal", "SessionSnapshot"]
