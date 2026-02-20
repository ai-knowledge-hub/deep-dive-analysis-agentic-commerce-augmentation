from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    default_version: str = "v1"
    required_inputs: tuple[str, ...] = ()
    default_inputs: Dict[str, Any] = field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    next_state: Optional[str] = None

    def normalize_inputs(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = dict(self.default_inputs)
        for key, value in dict(inputs or {}).items():
            normalized[str(key)] = value
        return normalized


_CAPABILITIES: Dict[str, CapabilitySpec] = {
    "freeze_retrieval_protocol": CapabilitySpec(
        name="freeze_retrieval_protocol",
        required_inputs=("experiment_id",),
        default_inputs={"retrieval_max_results": 5},
        side_effects=(
            "create_experiment_retrieval_snapshots",
            "update_experiment_state",
        ),
        next_state="retrieval_snapshots_ready",
    ),
    "run_control_baseline": CapabilitySpec(
        name="run_control_baseline",
        required_inputs=("experiment_id",),
        default_inputs={"retrieval_max_results": 5},
        side_effects=("create_experiment_run", "create_experiment_metric"),
        next_state="baseline_scored",
    ),
    "seed_hypotheses": CapabilitySpec(
        name="seed_hypotheses",
        required_inputs=("experiment_id",),
        side_effects=("create_experiment_hypotheses",),
        next_state="hypotheses_ready",
    ),
    "generate_variants": CapabilitySpec(
        name="generate_variants",
        required_inputs=("experiment_id",),
        default_inputs={
            "mode": "loop_evidence",
            "strategy": "both",
            "max_candidates": 3,
            "persist_count": 2,
        },
        side_effects=("create_experiment_variants",),
        next_state="variants_ready",
    ),
    "run_variant": CapabilitySpec(
        name="run_variant",
        required_inputs=("experiment_id",),
        default_inputs={"variant_selection": "top_1", "retrieval_max_results": 5},
        side_effects=("create_experiment_run", "create_experiment_metric"),
        next_state="experiment_run_completed",
    ),
    "request_synthetic_validation": CapabilitySpec(
        name="request_synthetic_validation",
        required_inputs=("experiment_id",),
        default_inputs={
            "provider": "openrouter",
            "mode": "in_app_byok",
            "auto_run": True,
            "variant_selection": "top_1",
            "prompt_version": "v1",
        },
        side_effects=("create_validation_job", "create_validation_result"),
        next_state="validation_completed",
    ),
    "review_validation_readiness": CapabilitySpec(
        name="review_validation_readiness",
        required_inputs=("experiment_id",),
        default_inputs={
            "variant_selection": "top_1",
            "prod_min_coverage": 0.2,
            "min_verified_runs": 3,
            "min_synthetic_results": 1,
        },
        side_effects=("read_validation_and_metrics",),
    ),
    "update_posterior_and_decisions": CapabilitySpec(
        name="update_posterior_and_decisions",
        required_inputs=("experiment_id",),
        side_effects=("create_experiment_metric", "create_decision_event"),
        next_state="posterior_updated",
    ),
    "recommend_next_action": CapabilitySpec(
        name="recommend_next_action",
        required_inputs=("experiment_id",),
        side_effects=("create_experiment_recommendation",),
    ),
    "promote_variant_lab": CapabilitySpec(
        name="promote_variant_lab",
        required_inputs=("experiment_id",),
        default_inputs={"variant_selection": "top_1", "require_promote_decision": True},
        side_effects=("create_analytics_event", "create_decision_event"),
    ),
    "promote_variant_prod": CapabilitySpec(
        name="promote_variant_prod",
        required_inputs=("experiment_id",),
        default_inputs={
            "variant_selection": "top_1",
            "require_promote_decision": True,
            "prod_min_coverage": 0.2,
            "min_verified_runs": 3,
            "min_synthetic_results": 1,
        },
        side_effects=("create_analytics_event", "create_decision_event"),
    ),
    "publish_copy_revision": CapabilitySpec(
        name="publish_copy_revision",
        required_inputs=("experiment_id",),
        default_inputs={"variant_selection": "top_1", "require_prod_promotion": True},
        side_effects=(
            "create_or_update_copy_revision",
            "update_product_description",
            "create_analytics_event",
            "create_decision_event",
        ),
    ),
}


def get_capability_spec(name: str) -> CapabilitySpec | None:
    return _CAPABILITIES.get(str(name or "").strip())


def capability_supported(name: str) -> bool:
    return get_capability_spec(name) is not None


def list_capability_specs() -> list[CapabilitySpec]:
    return list(_CAPABILITIES.values())


def next_state_for_capability(name: str) -> str | None:
    spec = get_capability_spec(name)
    return spec.next_state if spec else None


__all__ = [
    "CapabilitySpec",
    "get_capability_spec",
    "capability_supported",
    "list_capability_specs",
    "next_state_for_capability",
]
