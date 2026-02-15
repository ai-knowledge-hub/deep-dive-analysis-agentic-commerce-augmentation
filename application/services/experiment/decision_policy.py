from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal, Optional, Tuple

from application.services.loop.belief_update_service import clamp


# NOTE:
# - Keep this module side-effect free (pure functions only).
# - Persist the exact inputs + version alongside run metrics so decisions are reproducible.
DECISION_POLICY_VERSION = "v2_weighted_combo_2026-02-15"


DecisionAction = Literal["promote_variant", "iterate_variant", "reject_hypothesis"]
PromotionTier = Literal["lab", "prod"]


@dataclass(frozen=True)
class EvidenceSignal:
    # Directional effect in [-1, +1]. Positive means "better than baseline/control".
    effect: Optional[float] = None
    # Reliability proxy in [0, 1] (support size, consensus, recency, etc.).
    reliability: Optional[float] = None
    # Optional supporting details for audit/debug (kept lightweight).
    support_size: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class DecisionInputs:
    exp: EvidenceSignal
    syn: EvidenceSignal
    obs: EvidenceSignal
    coverage_obs: float = 0.0
    # Weight defaults (can be overridden by a future capability registry / policy registry).
    w_exp_base: float = 0.55
    w_syn_base: float = 0.35
    w_obs_base: float = 0.10
    # Observed weight schedule.
    w_obs_gain: float = 0.25
    w_obs_min: float = 0.10
    w_obs_max: float = 0.35
    # Decision thresholds are applied on a [0, 1] likelihood-like score.
    promote_threshold: float = 0.75
    iterate_threshold: float = 0.45
    # When true, keep experiment weight dominant and take extra observed weight from synthetic first.
    preserve_exp_weight: bool = True
    # Minimum observed coverage to call a promotion "prod" tier.
    prod_min_coverage: float = 0.20


@dataclass(frozen=True)
class DecisionOutputs:
    policy_version: str
    weights: Dict[str, float]
    combined_score: float  # [-1, +1]
    likelihood: float  # [0, 1]
    action: DecisionAction
    promotion_tier: Optional[PromotionTier] = None


def _reliability_adjusted(effect: Optional[float], reliability: Optional[float]) -> float:
    if effect is None:
        return 0.0
    r = clamp(float(reliability) if reliability is not None else 0.0)
    # Use sqrt reliability so low support doesn't dominate, but still contributes.
    return float(effect) * (r**0.5)


def _compute_weights(inputs: DecisionInputs) -> Dict[str, float]:
    # Start from base weights and adapt observed weight based on observed coverage.
    cov = clamp(float(inputs.coverage_obs), 0.0, 1.0)
    w_obs = clamp(
        float(inputs.w_obs_base) + float(inputs.w_obs_gain) * cov,
        float(inputs.w_obs_min),
        float(inputs.w_obs_max),
    )

    w_exp = clamp(float(inputs.w_exp_base))
    w_syn = clamp(float(inputs.w_syn_base))

    # Rebalance to incorporate adaptive w_obs while keeping weights normalized.
    # Strategy:
    # - keep experiment weight stable unless preserve_exp_weight=False
    # - take extra observed weight from synthetic first, then (optionally) experiment.
    total_base = w_exp + w_syn + clamp(float(inputs.w_obs_base))
    if total_base <= 0:
        return {"exp": 0.55, "syn": 0.35, "obs": 0.10}

    extra_obs = max(0.0, w_obs - clamp(float(inputs.w_obs_base)))
    w_syn_adj = max(0.0, w_syn - extra_obs)
    remaining_extra = max(0.0, extra_obs - (w_syn - w_syn_adj))

    w_exp_adj = w_exp
    if not inputs.preserve_exp_weight and remaining_extra > 0:
        w_exp_adj = max(0.0, w_exp_adj - remaining_extra)

    # Normalize to sum to 1.0.
    s = w_exp_adj + w_syn_adj + w_obs
    if s <= 0:
        return {"exp": 0.55, "syn": 0.35, "obs": 0.10}
    return {
        "exp": round(w_exp_adj / s, 6),
        "syn": round(w_syn_adj / s, 6),
        "obs": round(w_obs / s, 6),
    }


def decide(inputs: DecisionInputs) -> DecisionOutputs:
    weights = _compute_weights(inputs)
    exp_c = _reliability_adjusted(inputs.exp.effect, inputs.exp.reliability)
    syn_c = _reliability_adjusted(inputs.syn.effect, inputs.syn.reliability)
    obs_c = _reliability_adjusted(inputs.obs.effect, inputs.obs.reliability)

    combined = (
        weights["exp"] * exp_c + weights["syn"] * syn_c + weights["obs"] * obs_c
    )
    combined = max(-1.0, min(1.0, float(combined)))
    likelihood = clamp((combined + 1.0) / 2.0)

    if likelihood >= float(inputs.promote_threshold):
        action: DecisionAction = "promote_variant"
    elif likelihood >= float(inputs.iterate_threshold):
        action = "iterate_variant"
    else:
        action = "reject_hypothesis"

    tier: Optional[PromotionTier] = None
    if action == "promote_variant":
        tier = "prod" if float(inputs.coverage_obs) >= float(inputs.prod_min_coverage) else "lab"

    return DecisionOutputs(
        policy_version=DECISION_POLICY_VERSION,
        weights=weights,
        combined_score=round(combined, 6),
        likelihood=round(likelihood, 6),
        action=action,
        promotion_tier=tier,
    )


def as_audit_payload(
    *, inputs: DecisionInputs, outputs: DecisionOutputs
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Helper to persist structured inputs/outputs in metrics_json (still pure)."""
    return asdict(inputs), asdict(outputs)


__all__ = [
    "DECISION_POLICY_VERSION",
    "EvidenceSignal",
    "DecisionInputs",
    "DecisionOutputs",
    "decide",
    "as_audit_payload",
]

