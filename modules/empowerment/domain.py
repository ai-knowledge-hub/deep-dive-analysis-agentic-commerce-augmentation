"""Domain models for empowerment module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ConstraintSeverity(str, Enum):
    """Severity levels for constraint violations."""

    BLOCK = "block"  # Hard stop - cannot proceed
    WARN = "warn"  # Soft warning - can proceed with acknowledgment
    INFO = "info"  # Informational - logged but not blocking


class ManipulationPattern(str, Enum):
    """Known manipulation patterns (World A tactics)."""

    # Scarcity manipulation
    ARTIFICIAL_SCARCITY = "artificial_scarcity"  # "Only 3 left!"
    FAKE_COUNTDOWN = "fake_countdown"  # Timers that reset

    # Urgency manipulation
    TIME_PRESSURE = "time_pressure"  # "Limited time offer!"
    EXPIRING_DEAL = "expiring_deal"  # "Offer expires in 2 hours"

    # Social pressure
    SOCIAL_PROOF = "social_proof_pressure"  # "Everyone's buying this"
    FEAR_OF_MISSING_OUT = "fomo"  # "Don't miss out!"
    POPULARITY_PRESSURE = "popularity_pressure"  # "Trending now!"

    # Dark patterns
    HIDDEN_COSTS = "hidden_costs"  # Fees revealed at checkout
    FORCED_UPSELL = "forced_upsell"  # Pre-selected add-ons
    CONFIRM_SHAMING = "confirm_shaming"  # "No thanks, I don't want to save money"
    MISDIRECTION = "misdirection"  # Visual tricks to click wrong option
    ROACH_MOTEL = "roach_motel"  # Easy to get in, hard to get out

    # Cognitive overload
    OPTION_OVERLOAD = "option_overload"  # Too many choices to evaluate
    INFORMATION_HIDING = "information_hiding"  # Important details buried
    BAIT_AND_SWITCH = "bait_and_switch"  # Advertised item unavailable

    # Emotional manipulation
    GUILT_TRIPPING = "guilt_tripping"  # "Your cart is feeling lonely"
    FEAR_APPEAL = "fear_appeal"  # "Without this, you'll struggle"
    FLATTERY = "excessive_flattery"  # "You have great taste!"


@dataclass
class ConstraintViolation:
    """A detected constraint violation."""

    pattern: ManipulationPattern
    severity: ConstraintSeverity
    evidence: str  # What triggered the detection
    explanation: str  # Human-readable explanation
    recommendation: str  # What World B does instead


@dataclass
class ConstraintResult:
    """Result of constraint checking."""

    blocked: bool
    violations: List[ConstraintViolation] = field(default_factory=list)
    summary: str = ""

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def block_reasons(self) -> List[str]:
        return [
            v.explanation
            for v in self.violations
            if v.severity == ConstraintSeverity.BLOCK
        ]

    @property
    def warnings(self) -> List[str]:
        return [
            v.explanation
            for v in self.violations
            if v.severity == ConstraintSeverity.WARN
        ]


@dataclass
class EmpowermentMetric:
    """A single empowerment measurement with evidence."""

    name: str
    score: float
    evidence: List[str]


@dataclass
class GoalAlignmentResult:
    """Result of goal alignment assessment."""

    score: float
    aligned_goals: List[str]
    misaligned_goals: List[str]
    supporting_products: List[str]
    confidence_summary: Dict[str, float | Dict[str, float]]


@dataclass
class AlienationSignal:
    """Signal indicating potential user alienation."""

    label: str
    severity: float
    pattern: Optional[ManipulationPattern] = None


__all__ = [
    "EmpowermentMetric",
    "GoalAlignmentResult",
    "AlienationSignal",
    "ConstraintSeverity",
    "ManipulationPattern",
    "ConstraintViolation",
    "ConstraintResult",
]
