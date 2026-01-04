"""MCP tool for empowerment metrics."""

from __future__ import annotations

from typing import List

from src.empowerment.goal_alignment import assess
from src.memory.semantic import SemanticMemory


def run(recommendations: List[str]) -> dict:
    memory = SemanticMemory()
    goals = memory.get("goals")
    result = assess(goals, recommendations)
    return {
        "score": result.score,
        "aligned_goals": result.aligned_goals,
        "misaligned_goals": result.misaligned_goals,
    }
