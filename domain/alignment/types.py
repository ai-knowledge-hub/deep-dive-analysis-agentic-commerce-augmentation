"""Pure domain types for alignment scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class AlignmentScore:
    """Alignment score for a single product."""

    product_id: str
    score: float
    matched_capabilities: List[str]
    alignment_reasoning: str
    confidence: float
    low_confidence: bool = False


@dataclass
class AlignmentSummary:
    """Aggregate alignment summary across candidate products."""

    score: float
    aligned_goals: List[str]
    misaligned_goals: List[str]
    supporting_products: List[str]
    confidence_summary: Dict[str, float | Dict[str, float]]


__all__ = [
    "AlignmentScore",
    "AlignmentSummary",
]
