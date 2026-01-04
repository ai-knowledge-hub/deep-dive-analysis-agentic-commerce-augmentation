"""Agent that looks for alienation signals and enforces empowerment policies."""

from __future__ import annotations

from src.empowerment import alienation


class AutonomyGuardAgent:
    def check(self, rationale: str) -> dict:
        signal = alienation.detect(rationale)
        if not signal:
            return {"status": "clear"}
        return {"status": "flagged", "signal": signal.__dict__}
