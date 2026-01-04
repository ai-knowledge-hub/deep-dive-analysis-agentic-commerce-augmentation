"""AIS-inspired goal alignment scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class GoalAlignmentResult:
    score: float
    aligned_goals: List[str]
    misaligned_goals: List[str]


def assess(goals: List[str], recommendations: List[str]) -> GoalAlignmentResult:
    aligned = [goal for goal in goals if any(goal.lower() in rec.lower() for rec in recommendations)]
    misaligned = [goal for goal in goals if goal not in aligned]
    score = len(aligned) / max(len(goals), 1)
    return GoalAlignmentResult(score=score, aligned_goals=aligned, misaligned_goals=misaligned)
