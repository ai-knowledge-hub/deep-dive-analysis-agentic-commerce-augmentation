"""Intent domain models - unified Intent type and supporting models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class IntentDefinition:
    """Definition of an intent category from the taxonomy."""

    label: str
    domain: str
    keywords: List[str]
    questions: List[str]


@dataclass
class Intent:
    """Unified intent representation used throughout the system.

    This combines the previous Intent and IntentResult structures into a single class.
    """

    label: str
    confidence: float
    evidence: List[str]
    domain: str
    clarifying_questions: List[str]
    source: str = "keyword"

    def to_dict(self) -> Dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "label": self.label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "domain": self.domain,
            "clarifying_questions": self.clarifying_questions,
            "source": self.source,
        }


@dataclass
class IntentContext:
    """Context for intent classification including prior turns and goals."""

    turns: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)

    def add_turn(self, text: str) -> None:
        """Add a conversation turn."""
        self.turns.append(text)

    def add_goal(self, goal: str) -> None:
        """Add a user goal."""
        self.goals.append(goal)

    def summarize(self) -> str:
        """Create a text summary of the context."""
        joined_turns = " | ".join(self.turns)
        joined_goals = ", ".join(self.goals)
        return f"Turns: {joined_turns}\nGoals: {joined_goals}"


__all__ = ["Intent", "IntentDefinition", "IntentContext"]
