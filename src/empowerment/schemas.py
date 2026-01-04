"""Schemas shared across empowerment tooling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class EmpowermentMetric:
    name: str
    score: float
    evidence: List[str]
