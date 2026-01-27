"""Application service wrapper for alignment scoring.

During the strangler migration this delegates to infrastructure adapters.
"""

from __future__ import annotations

from typing import Any, List

from infrastructure.alignment.goal_alignment_gateway import assess as _assess
from infrastructure.alignment.goal_alignment_gateway import (
    score_products as _score_products,
)


class AlignmentService:
    def assess(
        self, goals: List[str], products: List[Any], *, use_semantic: bool = True
    ) -> Any:
        return _assess(goals, products, use_semantic=use_semantic)

    def score_products(
        self, goals: List[str], products: List[Any], *, use_semantic: bool = True
    ) -> list:
        return _score_products(goals, products, use_semantic=use_semantic) or []


alignment_service = AlignmentService()

__all__ = ["AlignmentService", "alignment_service"]
