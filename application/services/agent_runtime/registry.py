from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    tool_effect_class,
)


@dataclass(frozen=True)
class ToolSpec:
    id: str
    capability_name: str
    default_version: str = "v1"
    required_inputs: tuple[str, ...] = ()
    default_inputs: Dict[str, Any] = field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    next_state: Optional[str] = None
    effect_class: str = "write_low_risk"

    def normalize_inputs(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = dict(self.default_inputs)
        for key, value in dict(inputs or {}).items():
            normalized[str(key)] = value
        return normalized


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    tool_id: str
    default_version: str = "v1"
    required_inputs: tuple[str, ...] = ()
    default_inputs: Dict[str, Any] = field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    next_state: Optional[str] = None
    effect_class: str = "write_low_risk"

    def normalize_inputs(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = dict(self.default_inputs)
        for key, value in dict(inputs or {}).items():
            normalized[str(key)] = value
        return normalized


def _tool(
    *,
    capability_name: str,
    default_version: str = "v1",
    required_inputs: tuple[str, ...] = (),
    default_inputs: Dict[str, Any] | None = None,
    side_effects: tuple[str, ...] = (),
    next_state: Optional[str] = None,
) -> ToolSpec:
    tool_id = capability_to_tool_id(capability_name) or f"legacy.{capability_name}"
    return ToolSpec(
        id=tool_id,
        capability_name=capability_name,
        default_version=default_version,
        required_inputs=required_inputs,
        default_inputs=dict(default_inputs or {}),
        side_effects=side_effects,
        next_state=next_state,
        effect_class=tool_effect_class(tool_id) or "write_low_risk",
    )


_TOOLS: Dict[str, ToolSpec] = {
    "retrieval.freeze_protocol": _tool(
        capability_name="freeze_retrieval_protocol",
        required_inputs=("experiment_id",),
        default_inputs={"retrieval_max_results": 5},
        side_effects=(
            "create_experiment_retrieval_snapshots",
            "update_experiment_state",
        ),
        next_state="retrieval_snapshots_ready",
    ),
    "experiment.run_control_baseline": _tool(
        capability_name="run_control_baseline",
        required_inputs=("experiment_id",),
        default_inputs={"retrieval_max_results": 5},
        side_effects=("create_experiment_run", "create_experiment_metric"),
        next_state="baseline_scored",
    ),
    "hypothesis.seed": _tool(
        capability_name="seed_hypotheses",
        required_inputs=("experiment_id",),
        side_effects=("create_experiment_hypotheses",),
        next_state="hypotheses_ready",
    ),
    "variant.generate": _tool(
        capability_name="generate_variants",
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
    "experiment.run_variant": _tool(
        capability_name="run_variant",
        required_inputs=("experiment_id",),
        default_inputs={"variant_selection": "top_1", "retrieval_max_results": 5},
        side_effects=("create_experiment_run", "create_experiment_metric"),
        next_state="experiment_run_completed",
    ),
    "validation.request_synthetic": _tool(
        capability_name="request_synthetic_validation",
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
    "validation.review_readiness": _tool(
        capability_name="review_validation_readiness",
        required_inputs=("experiment_id",),
        default_inputs={
            "variant_selection": "top_1",
            "prod_min_coverage": 0.2,
            "min_verified_runs": 3,
            "min_synthetic_results": 1,
        },
        side_effects=("read_validation_and_metrics",),
    ),
    "learning.update_posterior_and_decisions": _tool(
        capability_name="update_posterior_and_decisions",
        required_inputs=("experiment_id",),
        side_effects=("create_experiment_metric", "create_decision_event"),
        next_state="posterior_updated",
    ),
    "policy.recommend_next_action": _tool(
        capability_name="recommend_next_action",
        required_inputs=("experiment_id",),
        side_effects=("create_experiment_recommendation",),
    ),
    "promotion.promote_lab": _tool(
        capability_name="promote_variant_lab",
        required_inputs=("experiment_id",),
        default_inputs={"variant_selection": "top_1", "require_promote_decision": True},
        side_effects=("create_analytics_event", "create_decision_event"),
    ),
    "promotion.promote_prod": _tool(
        capability_name="promote_variant_prod",
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
    "copy.publish_revision": _tool(
        capability_name="publish_copy_revision",
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

_CAPABILITIES: Dict[str, CapabilitySpec] = {
    tool.capability_name: CapabilitySpec(
        name=tool.capability_name,
        tool_id=tool.id,
        default_version=tool.default_version,
        required_inputs=tool.required_inputs,
        default_inputs=dict(tool.default_inputs),
        side_effects=tool.side_effects,
        next_state=tool.next_state,
        effect_class=tool.effect_class,
    )
    for tool in _TOOLS.values()
}


def get_tool_spec(tool_id: str) -> ToolSpec | None:
    return _TOOLS.get(str(tool_id or "").strip())


def tool_supported(tool_id: str) -> bool:
    return get_tool_spec(tool_id) is not None


def list_tool_specs() -> list[ToolSpec]:
    return list(_TOOLS.values())


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
    "ToolSpec",
    "get_tool_spec",
    "tool_supported",
    "list_tool_specs",
    "get_capability_spec",
    "capability_supported",
    "list_capability_specs",
    "next_state_for_capability",
]
