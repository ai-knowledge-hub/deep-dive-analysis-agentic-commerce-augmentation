"""Domain models for empowerment module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class EmpowermentMetric:
    """A single empowerment measurement with evidence."""

    name: str
    score: float
    evidence: List[str]


@dataclass
class GoalAlignmentResult:
    """Result of goal alignment assessment."""

    score: float
    aligned_goals: List[str]
    misaligned_goals: List[str]
    supporting_products: List[str]
    confidence_summary: Dict[str, float | Dict[str, float]]


@dataclass
class AlienationSignal:
    """Signal indicating potential user alienation."""

    label: str
    severity: float


__all__ = ["EmpowermentMetric", "GoalAlignmentResult", "AlienationSignal"]
