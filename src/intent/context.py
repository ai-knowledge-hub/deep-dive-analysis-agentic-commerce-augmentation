"""Helpers for gathering short-lived context like prior turns and goals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class IntentContext:
    turns: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)

    def add_turn(self, text: str) -> None:
        self.turns.append(text)

    def add_goal(self, goal: str) -> None:
        self.goals.append(goal)

    def summarize(self) -> str:
        joined_turns = " | ".join(self.turns)
        joined_goals = ", ".join(self.goals)
        return f"Turns: {joined_turns}\nGoals: {joined_goals}"
