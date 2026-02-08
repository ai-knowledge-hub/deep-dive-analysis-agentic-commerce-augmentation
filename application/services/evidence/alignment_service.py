"""Application service wrapper for alignment scoring.

During the strangler migration this delegates to infrastructure adapters.
"""

from __future__ import annotations

from typing import Any, List

from application.ports.deps import AppDeps


class AlignmentService:
    def __init__(self, deps: AppDeps) -> None:
        self._deps = deps

    def assess(
        self, goals: List[str], products: List[Any], *, use_semantic: bool = True
    ) -> Any:
        return self._deps.alignment_assess(goals, products, use_semantic=use_semantic)

    def score_products(
        self, goals: List[str], products: List[Any], *, use_semantic: bool = True
    ) -> list:
        return (
            self._deps.alignment_score_products(
                goals, products, use_semantic=use_semantic
            )
            or []
        )


__all__ = ["AlignmentService"]
