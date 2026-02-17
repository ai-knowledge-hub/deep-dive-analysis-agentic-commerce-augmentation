from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProposedAction:
    capability_name: str
    capability_version: Optional[str]
    inputs: Dict[str, Any]
    rationale: str
    confidence: float = 0.65

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_initial_plan(
    *,
    experiment_id: Optional[str],
    allowed_capabilities: List[str],
    capability_versions: Dict[str, Any],
) -> List[ProposedAction]:
    """
    Minimal v0 planner.

    - Produces a small, human-reviewable action queue.
    - Does not execute anything (execution is handled by AgentRuntime later).
    """
    allowed = {str(x).strip() for x in allowed_capabilities if str(x).strip()}
    versions = capability_versions or {}

    def v(name: str) -> Optional[str]:
        value = versions.get(name)
        return str(value) if isinstance(value, str) and value.strip() else None

    actions: List[ProposedAction] = []
    if experiment_id:
        base_inputs = {"experiment_id": experiment_id}
    else:
        base_inputs = {}

    if "freeze_retrieval_protocol" in allowed:
        actions.append(
            ProposedAction(
                capability_name="freeze_retrieval_protocol",
                capability_version=v("freeze_retrieval_protocol"),
                inputs=base_inputs,
                rationale="Freeze a retrieval snapshot set so variant comparisons are fair and time-drift resistant.",
                confidence=0.7,
            )
        )
    if "run_control_baseline" in allowed:
        actions.append(
            ProposedAction(
                capability_name="run_control_baseline",
                capability_version=v("run_control_baseline"),
                inputs=base_inputs,
                rationale="Score the control baseline on the frozen snapshot to unlock candidate runs (baseline-first gating).",
                confidence=0.7,
            )
        )
    if "seed_hypotheses" in allowed:
        actions.append(
            ProposedAction(
                capability_name="seed_hypotheses",
                capability_version=v("seed_hypotheses"),
                inputs=base_inputs,
                rationale="Derive and persist initial hypotheses from baseline deltas (missing winner signals).",
                confidence=0.65,
            )
        )
    if "generate_variants" in allowed:
        actions.append(
            ProposedAction(
                capability_name="generate_variants",
                capability_version=v("generate_variants"),
                inputs={**base_inputs, "mode": "draft"},
                rationale="Generate candidate variants linked to hypotheses (draft only until reviewed).",
                confidence=0.6,
            )
        )
    if "run_variant" in allowed:
        actions.append(
            ProposedAction(
                capability_name="run_variant",
                capability_version=v("run_variant"),
                inputs={**base_inputs, "variant_selection": "top_1"},
                rationale="Run a single candidate to collect early signal within budget (requires baseline gate).",
                confidence=0.55,
            )
        )
    if "request_synthetic_validation" in allowed:
        actions.append(
            ProposedAction(
                capability_name="request_synthetic_validation",
                capability_version=v("request_synthetic_validation"),
                inputs={**base_inputs, "mode": "in_app_byok"},
                rationale="Request synthetic validation jobs for the latest candidate to increase evidence reliability.",
                confidence=0.55,
            )
        )
    if "update_posterior_and_decisions" in allowed:
        actions.append(
            ProposedAction(
                capability_name="update_posterior_and_decisions",
                capability_version=v("update_posterior_and_decisions"),
                inputs=base_inputs,
                rationale="Compute posterior and decision outputs from combined experiment/synthetic/observed evidence.",
                confidence=0.6,
            )
        )
    return actions


__all__ = ["ProposedAction", "build_initial_plan"]

