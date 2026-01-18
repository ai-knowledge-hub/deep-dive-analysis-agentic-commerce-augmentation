"""Alignment module - intent-product scoring and reasoning."""

from modules.alignment.domain import AlignmentScore, AlignmentSummary
from modules.alignment.goal_alignment import assess, score_products
from modules.alignment.optimizer import rank
from modules.alignment.llm_reasoner import reason_about_products

__all__ = [
    "AlignmentScore",
    "AlignmentSummary",
    "assess",
    "score_products",
    "rank",
    "reason_about_products",
]
