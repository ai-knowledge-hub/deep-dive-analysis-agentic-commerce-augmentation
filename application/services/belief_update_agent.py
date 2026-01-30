from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class BeliefUpdate:
    summary: str
    recommendation: str
    confidence: float
    metadata: Dict[str, Any]


class BeliefUpdateAgent:
    """Rule-based belief summarizer for experiment outcomes."""

    def build_update(
        self,
        *,
        experiment: Dict[str, Any],
        variant: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> BeliefUpdate:
        hypothesis = experiment.get("hypothesis") or {}
        metric_name = str(hypothesis.get("metric") or "win_rate")
        direction = str(hypothesis.get("direction") or "increase")
        variant_label = variant.get("label") or "variant"

        win_rate = float(metrics.get("win_rate") or 0.0)
        avg_score = metrics.get("avg_score")
        avg_score_value = float(avg_score) if avg_score is not None else None

        observed_value = win_rate if metric_name == "win_rate" else avg_score_value
        support = _supports_hypothesis(direction, observed_value)

        summary_parts = [
            f"{variant_label} achieved win rate {win_rate:.2f}"
            + (
                f" and avg score {avg_score_value:.2f}."
                if avg_score_value is not None
                else "."
            ),
        ]
        if metric_name:
            summary_parts.append(f"Hypothesis targeted {metric_name} to {direction}.")
        summary_parts.append(
            "Result supports hypothesis."
            if support
            else "Result does not support hypothesis."
        )

        recommendation = (
            f"Keep and iterate on '{variant_label}' — evidence supports the hypothesis."
            if support
            else f"Revise the hypothesis or adjust '{variant_label}' before scaling."
        )

        confidence = _derive_confidence(win_rate, avg_score_value)

        metadata = {
            "summary": " ".join(summary_parts),
            "metric": metric_name,
            "direction": direction,
            "support": support,
            "variant_payload_keys": sorted((variant.get("payload") or {}).keys()),
        }

        return BeliefUpdate(
            summary=metadata["summary"],
            recommendation=recommendation,
            confidence=confidence,
            metadata=metadata,
        )


def _supports_hypothesis(direction: str, value: float | None) -> bool:
    if value is None:
        return False
    if direction.lower() in {"increase", "up", "higher"}:
        return value >= 0.5
    if direction.lower() in {"decrease", "down", "lower"}:
        return value <= 0.5
    return value >= 0.5


def _derive_confidence(win_rate: float, avg_score: float | None) -> float:
    if avg_score is None:
        return round(win_rate, 3)
    return round((win_rate + avg_score) / 2, 3)


__all__ = ["BeliefUpdateAgent", "BeliefUpdate"]
