"""Compatibility shim for commerce plan building.

Canonical implementation lives in `application.services.commerce_plan_builder`.

This module preserves test monkeypatch seams:
- `modules.commerce.plan_builder.product_search`
"""

from __future__ import annotations

from modules.commerce.search import search as product_search
from modules.commerce.compare import compare
from modules.intentionality.profiling import build_profile

from application.services.commerce_plan_builder import CommercePlanBuilder


class PlanBuilder:
    confidence_threshold: float = 0.65
    fallback_limit: int = 3

    def __init__(self) -> None:
        self._impl = CommercePlanBuilder(
            search_fn=product_search,
            compare_fn=compare,
            build_profile_fn=build_profile,
        )

    def build_plan(self, *args, **kwargs):
        return self._impl.build_plan(*args, **kwargs)


__all__ = ["PlanBuilder", "product_search"]

