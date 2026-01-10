"""Domain models for values clarification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ClarificationTurn:
    """A single turn in the clarification dialogue."""

    speaker: str
    content: str

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {"speaker": self.speaker, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "ClarificationTurn":
        """Deserialize from dictionary."""
        return cls(speaker=data["speaker"], content=data["content"])


@dataclass
class ClarificationState:
    """State of the values clarification dialogue."""

    query: str
    turns: List[ClarificationTurn] = field(default_factory=list)
    extracted_goals: List[str] = field(default_factory=list)
    ready_for_products: bool = False
    metadata: dict = field(default_factory=dict)

    def add_turn(self, speaker: str, content: str) -> None:
        """Add a turn to the dialogue."""
        self.turns.append(ClarificationTurn(speaker=speaker, content=content))

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "query": self.query,
            "turns": [turn.to_dict() for turn in self.turns],
            "extracted_goals": self.extracted_goals,
            "ready_for_products": self.ready_for_products,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClarificationState":
        """Deserialize from dictionary."""
        turns = [ClarificationTurn.from_dict(item) for item in data.get("turns", [])]
        return cls(
            query=data["query"],
            turns=turns,
            extracted_goals=data.get("extracted_goals", []),
            ready_for_products=data.get("ready_for_products", False),
            metadata=data.get("metadata", {}),
        )


__all__ = ["ClarificationTurn", "ClarificationState"]
