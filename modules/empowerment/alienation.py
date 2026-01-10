"""Alienation heuristics used by the autonomy guard."""

from __future__ import annotations

from modules.empowerment.domain import AlienationSignal


def detect(rationale: str) -> AlienationSignal | None:
    """Detect signs of user alienation from the rationale."""
    lowered = rationale.lower()
    if "overwhelmed" in lowered:
        return AlienationSignal(label="overload", severity=0.7)
    if "confused" in lowered:
        return AlienationSignal(label="ambiguity", severity=0.5)
    return None


__all__ = ["detect"]
