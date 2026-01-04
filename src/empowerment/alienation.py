"""Alienation heuristics used by the autonomy guard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlienationSignal:
    label: str
    severity: float


def detect(rationale: str) -> AlienationSignal | None:
    lowered = rationale.lower()
    if "overwhelmed" in lowered:
        return AlienationSignal(label="overload", severity=0.7)
    if "confused" in lowered:
        return AlienationSignal(label="ambiguity", severity=0.5)
    return None
