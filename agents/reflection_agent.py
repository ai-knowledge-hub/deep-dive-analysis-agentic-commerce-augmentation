"""Agent that triggers empowerment-aware reflection."""

from __future__ import annotations

from src.empowerment import reflection


class ReflectionAgent:
    def reflect(self, plan: dict) -> str:
        entries = [f"Plan query: {plan.get('query')}", f"Products: {len(plan.get('product_ids', []))}"]
        return reflection.generate(entries)
