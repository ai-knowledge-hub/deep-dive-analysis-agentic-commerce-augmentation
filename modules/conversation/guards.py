"""Autonomy guard agent for empowerment policies."""

from __future__ import annotations

from typing import List

from modules.empowerment import alienation
from modules.empowerment.constraints import check_constraints, result_to_dict


class AutonomyGuardAgent:
    """Agent that looks for alienation signals and enforces empowerment policies."""

    def check(
        self,
        rationale: str,
        clarifications: List[str] | None = None,
        products: List[dict] | None = None,
    ) -> dict:
        """Check for alienation signals and low confidence products."""
        signal = alienation.detect(rationale)
        constraints = check_constraints(rationale, products=products or [])
        flags: List[str] = []
        if clarifications:
            flags.extend(clarifications)
        if products and any(
            product.get("confidence", 0.0) < 0.5 for product in products
        ):
            flags.append(
                "Some recommendations fall below confidence safeguards; confirm consent before action."
            )
        if signal:
            flags.append(
                f"Alienation signal detected: {signal.label} (severity {signal.severity})"
            )
        if constraints.has_violations:
            flags.append(constraints.summary)
        if constraints.blocked:
            return {
                "status": "blocked",
                "flags": flags,
                "constraints": result_to_dict(constraints),
                "summary": constraints.summary,
            }
        if flags:
            return {
                "status": "needs_review",
                "flags": flags,
                "constraints": result_to_dict(constraints),
                "summary": constraints.summary,
            }
        return {"status": "clear", "constraints": result_to_dict(constraints)}


__all__ = ["AutonomyGuardAgent"]
