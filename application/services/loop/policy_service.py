from __future__ import annotations

import logging
from typing import Dict, List, Optional

from application.ports.deps import AppDeps

logger = logging.getLogger(__name__)


class PolicyService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def record_decision(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        policy_action: str,
        uncertainty: Optional[float] = None,
        expected_gain: Optional[float] = None,
        selected_reason: Optional[str] = None,
    ):
        decision = self._deps.decision_events.create_decision_event(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            policy_action=policy_action,
            uncertainty=uncertainty,
            expected_gain=expected_gain,
            selected_reason=selected_reason,
        )
        logger.info(
            "policy_decision client_id=%s brand_id=%s product_id=%s action=%s uncertainty=%s expected_gain=%s reason=%s",
            client_id,
            brand_id,
            product_id,
            policy_action,
            uncertainty,
            expected_gain,
            selected_reason,
        )
        return decision

    def latest_decision(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
    ):
        return self._deps.decision_events.get_latest_decision_event(
            client_id=client_id, brand_id=brand_id, product_id=product_id
        )

    def choose_action(
        self,
        *,
        client_id: str,
        provider: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        uncertainty: float = 0.5,
        expected_gain: float = 0.5,
        actions: Optional[List[str]] = None,
    ) -> Dict[str, float | str]:
        actions = actions or [
            "optimize_copy",
            "expand_battery",
            "validate",
            "clarify",
            "update_belief_only",
        ]
        profile = self._deps.calibration_profiles.get_calibration_profile(
            client_id=client_id,
            brand_id=brand_id,
            provider=provider,
        ) or self._deps.calibration_profiles.get_calibration_profile(
            client_id=client_id,
            brand_id=None,
            provider=provider,
        )
        weights = (profile or {}).get("metric_weights") or {}
        uncertainty_weight = float(weights.get("uncertainty_weight", 1.0))
        gain_weight = float(weights.get("gain_weight", 1.0))
        drift = float((profile or {}).get("drift_score", 0.0))

        scored: list[tuple[str, float]] = []
        for action in actions:
            action_bias = _action_bias(action)
            score = (
                action_bias
                + (uncertainty * uncertainty_weight * 0.5)
                + (expected_gain * gain_weight * 0.5)
                - (
                    drift * 0.2
                    if action in {"optimize_copy", "expand_battery"}
                    else 0.0
                )
            )
            scored.append((action, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        chosen, chosen_score = scored[0]
        logger.info(
            "policy_choose_action client_id=%s brand_id=%s product_id=%s provider=%s drift=%.4f action=%s score=%.4f options=%s",
            client_id,
            brand_id,
            product_id,
            provider,
            drift,
            chosen,
            chosen_score,
            ",".join(actions),
        )
        return {"action": chosen, "score": chosen_score}


def _action_bias(action: str) -> float:
    if action == "validate":
        return 0.5
    if action == "clarify":
        return 0.45
    if action == "optimize_copy":
        return 0.4
    if action == "expand_battery":
        return 0.35
    if action == "update_belief_only":
        return 0.25
    return 0.2


__all__ = ["PolicyService"]
