"""Pure goal clarification state types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class GoalClarificationTurn:
    """A single turn in the clarification dialogue."""

    speaker: str
    content: str

    def to_dict(self) -> dict:
        return {"speaker": self.speaker, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "GoalClarificationTurn":
        return cls(speaker=data["speaker"], content=data["content"])


@dataclass
class GoalClarificationState:
    """State of the goal clarification dialogue."""

    query: str
    turns: List[GoalClarificationTurn] = field(default_factory=list)
    extracted_goals: List[str] = field(default_factory=list)
    ready_for_products: bool = False
    metadata: dict = field(default_factory=dict)

    def add_turn(self, speaker: str, content: str) -> None:
        self.turns.append(GoalClarificationTurn(speaker=speaker, content=content))

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "turns": [turn.to_dict() for turn in self.turns],
            "extracted_goals": self.extracted_goals,
            "ready_for_products": self.ready_for_products,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GoalClarificationState":
        turns = [
            GoalClarificationTurn.from_dict(item) for item in data.get("turns", [])
        ]
        return cls(
            query=data["query"],
            turns=turns,
            extracted_goals=data.get("extracted_goals", []),
            ready_for_products=data.get("ready_for_products", False),
            metadata=data.get("metadata", {}),
        )


__all__ = ["GoalClarificationState", "GoalClarificationTurn"]

