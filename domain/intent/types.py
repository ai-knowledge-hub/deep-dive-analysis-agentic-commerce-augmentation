"""Pure intent domain types.

These types are shared across conversation, evidence, and simulation flows.
They intentionally contain no IO, DB, or LLM dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class IntentDefinition:
    """Definition of an intent category from the taxonomy."""

    label: str
    domain: str
    keywords: List[str]
    questions: List[str]


@dataclass
class InferredIntent:
    """Structured inferred intent output for discovery alignment."""

    primary_goal: str
    secondary_goals: List[str] = field(default_factory=list)
    underlying_needs: List[str] = field(default_factory=list)
    context_signals: List[str] = field(default_factory=list)
    confidence: float = 0.0
    domain: str | None = None
    source: str = "keyword"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_goal": self.primary_goal,
            "secondary_goals": list(self.secondary_goals),
            "underlying_needs": list(self.underlying_needs),
            "context_signals": list(self.context_signals),
            "confidence": self.confidence,
            "domain": self.domain,
            "source": self.source,
        }


@dataclass
class IntentContext:
    """Context for intent inference including history and preferences."""

    query: str
    session_history: List[str] = field(default_factory=list)
    user_goals: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)

    def summarize(self) -> str:
        joined_turns = " | ".join(self.session_history)
        joined_goals = ", ".join(self.user_goals)
        return (
            f"Query: {self.query}\n"
            f"Turns: {joined_turns}\n"
            f"Goals: {joined_goals}\n"
            f"Preferences: {self.user_preferences}"
        )


__all__ = ["InferredIntent", "IntentContext", "IntentDefinition"]

