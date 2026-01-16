"""Constraint detection for World B guardrails."""

from __future__ import annotations

from typing import Iterable, List

from modules.empowerment.domain import (
    ConstraintResult,
    ConstraintSeverity,
    ConstraintViolation,
    ManipulationPattern,
)


def _find_matches(text: str, keywords: Iterable[str]) -> List[str]:
    return [phrase for phrase in keywords if phrase in text]


def check_constraints(
    rationale: str, products: List[dict] | None = None
) -> ConstraintResult:
    """Check rationale and product metadata for manipulation patterns."""
    lowered = (rationale or "").lower()
    violations: List[ConstraintViolation] = []

    patterns = [
        (
            ManipulationPattern.ARTIFICIAL_SCARCITY,
            ConstraintSeverity.BLOCK,
            ["only 3 left", "limited stock", "selling out", "last chance"],
            "Scarcity pressure detected.",
            "Remove scarcity language and present availability neutrally.",
        ),
        (
            ManipulationPattern.TIME_PRESSURE,
            ConstraintSeverity.BLOCK,
            ["limited time", "act now", "expires in", "today only"],
            "Time pressure detected.",
            "Offer a calm timeline and a save-for-later option.",
        ),
        (
            ManipulationPattern.EXPIRING_DEAL,
            ConstraintSeverity.WARN,
            ["deal ends", "offer expires", "ending soon"],
            "Expiring deal language detected.",
            "Provide alternatives and explain tradeoffs.",
        ),
        (
            ManipulationPattern.SOCIAL_PROOF,
            ConstraintSeverity.WARN,
            ["everyone's buying", "most popular", "trending", "bestseller"],
            "Social pressure detected.",
            "Reframe as optional and include alternatives.",
        ),
        (
            ManipulationPattern.POPULARITY_PRESSURE,
            ConstraintSeverity.WARN,
            ["people like you", "top rated", "hot right now"],
            "Popularity pressure detected.",
            "Avoid social ranking; emphasize fit to goals.",
        ),
        (
            ManipulationPattern.FEAR_OF_MISSING_OUT,
            ConstraintSeverity.WARN,
            ["don't miss out", "missing out", "fomo"],
            "FOMO language detected.",
            "Replace with transparent tradeoffs.",
        ),
        (
            ManipulationPattern.CONFIRM_SHAMING,
            ConstraintSeverity.WARN,
            [
                "no thanks, i hate saving",
                "i don't want to save",
                "no, i prefer to waste",
            ],
            "Confirm-shaming language detected.",
            "Offer neutral opt-out wording.",
        ),
        (
            ManipulationPattern.FORCED_UPSELL,
            ConstraintSeverity.WARN,
            ["preselected add-on", "auto-added", "upgrade selected"],
            "Forced upsell pattern detected.",
            "Let users explicitly opt into add-ons.",
        ),
        (
            ManipulationPattern.MISDIRECTION,
            ConstraintSeverity.WARN,
            ["tiny print", "hidden button", "greyed out"],
            "Misdirection pattern detected.",
            "Present clear choices with equal visibility.",
        ),
        (
            ManipulationPattern.ROACH_MOTEL,
            ConstraintSeverity.WARN,
            ["cancel anytime", "hard to cancel", "call to cancel"],
            "Roach-motel pattern detected.",
            "Clarify cancellation steps and alternatives.",
        ),
        (
            ManipulationPattern.BAIT_AND_SWITCH,
            ConstraintSeverity.BLOCK,
            ["unavailable", "out of stock", "similar item instead"],
            "Bait-and-switch signal detected.",
            "Disclose availability and avoid substitution pressure.",
        ),
        (
            ManipulationPattern.GUILT_TRIPPING,
            ConstraintSeverity.WARN,
            ["don't let your", "cart is lonely", "sad without you"],
            "Guilt-tripping language detected.",
            "Remove emotional pressure and provide facts.",
        ),
        (
            ManipulationPattern.HIDDEN_COSTS,
            ConstraintSeverity.BLOCK,
            ["fees apply", "taxes at checkout", "shipping calculated later"],
            "Potential hidden costs detected.",
            "Disclose full price upfront when possible.",
        ),
        (
            ManipulationPattern.OPTION_OVERLOAD,
            ConstraintSeverity.WARN,
            ["too many choices", "overwhelmed"],
            "Option overload signal detected.",
            "Reduce to top 3 and offer a guided comparison.",
        ),
    ]

    for pattern, severity, keywords, explanation, recommendation in patterns:
        matches = _find_matches(lowered, keywords)
        if matches:
            violations.append(
                ConstraintViolation(
                    pattern=pattern,
                    severity=severity,
                    evidence=", ".join(matches),
                    explanation=explanation,
                    recommendation=recommendation,
                )
            )

    if products:
        low_conf = [p for p in products if p.get("confidence", 1.0) < 0.3]
        if low_conf:
            violations.append(
                ConstraintViolation(
                    pattern=ManipulationPattern.INFORMATION_HIDING,
                    severity=ConstraintSeverity.WARN,
                    evidence="low-confidence products present",
                    explanation="Some products lack sufficient information.",
                    recommendation="Confirm details or reduce to verified options.",
                )
            )

    blocked = any(v.severity == ConstraintSeverity.BLOCK for v in violations)
    summary = (
        "No constraint violations detected."
        if not violations
        else (
            "Blocking violations detected."
            if blocked
            else "Constraint warnings detected."
        )
    )
    return ConstraintResult(blocked=blocked, violations=violations, summary=summary)


def result_to_dict(result: ConstraintResult) -> dict:
    return {
        "blocked": result.blocked,
        "summary": result.summary,
        "violations": [
            {
                "pattern": v.pattern.value,
                "severity": v.severity.value,
                "evidence": v.evidence,
                "explanation": v.explanation,
                "recommendation": v.recommendation,
            }
            for v in result.violations
        ],
    }


__all__ = ["check_constraints", "result_to_dict"]
