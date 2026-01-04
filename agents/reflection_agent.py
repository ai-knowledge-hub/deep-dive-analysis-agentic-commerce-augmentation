"""Agent that triggers empowerment-aware reflection."""

from __future__ import annotations

from src.empowerment import reflection


class ReflectionAgent:
    def reflect(self, plan: dict) -> str:
        products = plan.get("products", [])
        data_quality = plan.get("data_quality", {})
        entries = [
            f"Plan query: {plan.get('query')}",
            f"Products considered: {len(products)}",
            f"Average data confidence: {data_quality.get('average_confidence', 0.0)}",
        ]
        clarifications = plan.get("clarifications", [])
        entries.extend(f"Clarification: {message}" for message in clarifications)
        return reflection.generate(entries)
