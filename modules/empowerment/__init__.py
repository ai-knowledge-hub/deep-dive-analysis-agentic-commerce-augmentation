"""Empowerment module - goal alignment, alienation detection, and reflection."""

from modules.empowerment.domain import (
    AlienationSignal,
    EmpowermentMetric,
    GoalAlignmentResult,
)
from modules.empowerment.goal_alignment import assess
from modules.empowerment.alienation import detect
from modules.empowerment.reflection import generate_reflection
from modules.empowerment.optimizer import rank
from modules.empowerment.llm_reasoner import reason_about_products

__all__ = [
    "AlienationSignal",
    "EmpowermentMetric",
    "GoalAlignmentResult",
    "assess",
    "detect",
    "generate_reflection",
    "rank",
    "reason_about_products",
]
