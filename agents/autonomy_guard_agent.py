"""Agent that looks for alienation signals and enforces empowerment policies."""

from __future__ import annotations

from typing import List

from src.empowerment import alienation


class AutonomyGuardAgent:
    def check(self, rationale: str, clarifications: List[str] | None = None, products: List[dict] | None = None) -> dict:
        signal = alienation.detect(rationale)
        flags: List[str] = []
        if clarifications:
            flags.extend(clarifications)
        if products and any(product.get("confidence", 0.0) < 0.5 for product in products):
            flags.append("Some recommendations fall below confidence safeguards; confirm consent before action.")
        if signal:
            flags.append(f"Alienation signal detected: {signal.label} (severity {signal.severity})")
        if flags:
            return {"status": "needs_review", "flags": flags}
        return {"status": "clear"}
