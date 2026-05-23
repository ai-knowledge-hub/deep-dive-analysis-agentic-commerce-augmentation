from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    tool_effect_class,
)

REGISTRY_VERSION = "agent-runtime-static-v1"
SUPPORTED_RUN_MODES = ("plan_only", "auto_execute_safe")


@dataclass(frozen=True)
class ToolSpec:
    id: str
    capability_name: str
    summary: str = ""
    default_version: str = "v1"
    required_inputs: tuple[str, ...] = ()
    default_inputs: Dict[str, Any] = field(default_factory=dict)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    review_checklist: tuple[str, ...] = ()
    owner_principal_id: str = "platform.agent-runtime"
    steward_team: str = "agent-runtime"
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
    summary: str = ""
    default_version: str = "v1"
    required_inputs: tuple[str, ...] = ()
    default_inputs: Dict[str, Any] = field(default_factory=dict)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    review_checklist: tuple[str, ...] = ()
    owner_principal_id: str = "platform.agent-runtime"
    steward_team: str = "agent-runtime"
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
    summary: str,
    default_version: str = "v1",
    required_inputs: tuple[str, ...] = (),
    default_inputs: Dict[str, Any] | None = None,
    input_properties: Dict[str, Any] | None = None,
    output_properties: Dict[str, Any] | None = None,
    output_required: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
    review_checklist: tuple[str, ...] = (),
    next_state: Optional[str] = None,
) -> ToolSpec:
    tool_id = capability_to_tool_id(capability_name) or f"legacy.{capability_name}"
    defaults = dict(default_inputs or {})
    owner_principal_id, steward_team = _ownership_for_tool(tool_id)
    return ToolSpec(
        id=tool_id,
        capability_name=capability_name,
        summary=summary,
        default_version=default_version,
        required_inputs=required_inputs,
        default_inputs=defaults,
        input_schema=_schema(
            required=required_inputs,
            properties={
                **_default_input_properties(defaults),
                **dict(input_properties or {}),
            },
        ),
        output_schema=_schema(
            required=output_required,
            properties=dict(output_properties or {}),
        ),
        side_effects=side_effects,
        review_checklist=review_checklist,
        owner_principal_id=owner_principal_id,
        steward_team=steward_team,
        next_state=next_state,
        effect_class=tool_effect_class(tool_id) or "write_low_risk",
    )


def _schema(*, required: tuple[str, ...], properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": True,
    }


def _default_input_properties(defaults: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: _property_for_value(value) for key, value in defaults.items()}


def _property_for_value(value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean", "default": value}
    if isinstance(value, int):
        return {"type": "integer", "default": value}
    if isinstance(value, float):
        return {"type": "number", "default": value}
    return {"type": "string", "default": value}


def _ownership_for_tool(tool_id: str) -> tuple[str, str]:
    if tool_id.startswith("validation."):
        return ("platform.validation", "validation-ops")
    if tool_id.startswith("promotion.") or tool_id.startswith("copy."):
        return ("platform.commerce-governance", "commerce-governance")
    if tool_id.startswith("policy."):
        return ("platform.agent-policy", "agent-policy")
    return ("platform.commerce-optimization", "commerce-optimization")


_TOOLS: Dict[str, ToolSpec] = {
    "retrieval.freeze_protocol": _tool(
        capability_name="freeze_retrieval_protocol",
        summary="Freeze retrieval snapshots for fair experiment comparisons.",
        required_inputs=("experiment_id",),
        input_properties={"experiment_id": {"type": "string"}},
        output_properties={"snapshot_version": {"type": "integer"}},
        default_inputs={"retrieval_max_results": 5},
        side_effects=(
            "create_experiment_retrieval_snapshots",
            "update_experiment_state",
        ),
        review_checklist=("Confirm the experiment battery is ready.",),
        next_state="retrieval_snapshots_ready",
    ),
    "experiment.run_control_baseline": _tool(
        capability_name="run_control_baseline",
        summary="Run the control variant on frozen retrieval snapshots.",
        required_inputs=("experiment_id",),
        input_properties={"experiment_id": {"type": "string"}},
        output_properties={
            "metric_id": {"type": "string"},
            "variant_id": {"type": "string"},
        },
        output_required=("metric_id", "variant_id"),
        default_inputs={"retrieval_max_results": 5},
        side_effects=("create_experiment_run", "create_experiment_metric"),
        review_checklist=("Confirm retrieval snapshots are frozen.",),
        next_state="baseline_scored",
    ),
    "hypothesis.seed": _tool(
        capability_name="seed_hypotheses",
        summary="Create hypotheses from baseline gaps and winner-signal deltas.",
        required_inputs=("experiment_id",),
        input_properties={"experiment_id": {"type": "string"}},
        output_properties={"hypothesis_ids": {"type": "array"}},
        side_effects=("create_experiment_hypotheses",),
        review_checklist=("Review repeated missing-winner signals.",),
        next_state="hypotheses_ready",
    ),
    "variant.generate": _tool(
        capability_name="generate_variants",
        summary="Generate candidate variants from evidence and hypotheses.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "max_candidates": {"type": "integer"},
            "persist_count": {"type": "integer"},
        },
        output_properties={"created_variants": {"type": "array"}},
        output_required=("created_variants",),
        default_inputs={
            "mode": "loop_evidence",
            "strategy": "both",
            "max_candidates": 3,
            "persist_count": 2,
        },
        side_effects=("create_experiment_variants",),
        review_checklist=(
            "Review generated copy and provenance before running variants.",
        ),
        next_state="variants_ready",
    ),
    "experiment.run_variant": _tool(
        capability_name="run_variant",
        summary="Execute one candidate variant against the frozen snapshot set.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "variant_id": {"type": "string"},
            "variant_selection": {"type": "string"},
            "retrieval_max_results": {"type": "integer"},
        },
        output_properties={
            "metric_id": {"type": "string"},
            "variant_id": {"type": "string"},
            "snapshot_version": {"type": "integer"},
        },
        output_required=("metric_id", "variant_id"),
        default_inputs={"variant_selection": "top_1", "retrieval_max_results": 5},
        side_effects=("create_experiment_run", "create_experiment_metric"),
        review_checklist=("Compare the metric against control before promotion.",),
        next_state="experiment_run_completed",
    ),
    "validation.request_synthetic": _tool(
        capability_name="request_synthetic_validation",
        summary="Request synthetic validation for the selected experiment/variant.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "provider": {"type": "string"},
            "auto_run": {"type": "boolean"},
            "variant_id": {"type": "string"},
        },
        output_properties={"validation_job_id": {"type": "string"}},
        output_required=("validation_job_id",),
        default_inputs={
            "provider": "openrouter",
            "mode": "in_app_byok",
            "auto_run": True,
            "variant_selection": "top_1",
            "prompt_version": "v1",
        },
        side_effects=("create_validation_job", "create_validation_result"),
        review_checklist=("Confirm provider configuration and cost posture.",),
        next_state="validation_completed",
    ),
    "validation.review_readiness": _tool(
        capability_name="review_validation_readiness",
        summary="Review validation and promotion readiness gates without mutating state.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "prod_min_coverage": {"type": "number"},
            "min_verified_runs": {"type": "integer"},
            "min_synthetic_results": {"type": "integer"},
        },
        output_properties={
            "variant_id": {"type": "string"},
            "readiness_state": {"type": "string"},
            "gates": {"type": "object"},
        },
        output_required=("variant_id", "readiness_state"),
        default_inputs={
            "variant_selection": "top_1",
            "prod_min_coverage": 0.2,
            "min_verified_runs": 3,
            "min_synthetic_results": 1,
        },
        side_effects=("read_validation_and_metrics",),
        review_checklist=(
            "Inspect validation coverage and observed/synthetic agreement.",
        ),
    ),
    "protocol.readiness_check": _tool(
        capability_name="check_protocol_readiness",
        summary="Run a read-only ACP/UCP readiness check through the adapter spine.",
        required_inputs=("product_id",),
        input_properties={
            "product_id": {"type": "string"},
            "protocols": {
                "type": "array",
                "items": {"type": "string", "enum": ["ucp", "acp"]},
            },
        },
        output_properties={
            "product_id": {"type": "string"},
            "protocol_readiness": {"type": "array"},
            "receipt": {"type": "object"},
            "receipt_id": {"type": "string"},
        },
        output_required=("product_id", "protocol_readiness", "receipt_id"),
        default_inputs={"protocols": ["ucp", "acp"]},
        side_effects=("read_product_protocol_metadata",),
        review_checklist=(
            "Confirm readiness is read-only before using protocol fallback evidence.",
        ),
    ),
    "protocol.discover_candidates": _tool(
        capability_name="discover_protocol_candidates",
        summary="Discover ACP/UCP candidate products through the adapter spine.",
        required_inputs=("query",),
        input_properties={
            "query": {"type": "string"},
            "brand_id": {"type": "string"},
            "protocol": {"type": "string", "enum": ["ucp", "acp"]},
            "limit": {"type": "integer"},
            "inferred_intent": {"type": "object"},
        },
        output_properties={
            "structured_query": {"type": "object"},
            "candidates": {"type": "array"},
            "summary": {"type": "object"},
            "receipt": {"type": "object"},
            "receipt_id": {"type": "string"},
        },
        output_required=("structured_query", "candidates", "summary", "receipt_id"),
        default_inputs={"limit": 10},
        side_effects=("read_protocol_candidates",),
        review_checklist=(
            "Confirm protocol discovery is read-only before using candidate evidence.",
        ),
    ),
    "learning.update_posterior_and_decisions": _tool(
        capability_name="update_posterior_and_decisions",
        summary="Refresh posterior and decision outputs from latest evidence.",
        required_inputs=("experiment_id",),
        input_properties={"experiment_id": {"type": "string"}},
        output_properties={
            "new_metric_id": {"type": "string"},
            "source_metric_id": {"type": "string"},
            "variant_id": {"type": "string"},
        },
        output_required=("new_metric_id", "variant_id"),
        side_effects=("create_experiment_metric", "create_decision_event"),
        review_checklist=(
            "Review evidence freshness before treating decisions as final.",
        ),
        next_state="posterior_updated",
    ),
    "policy.recommend_next_action": _tool(
        capability_name="recommend_next_action",
        summary="Recommend the safest next action under current constraints.",
        required_inputs=("experiment_id",),
        input_properties={"experiment_id": {"type": "string"}},
        output_properties={"recommendation": {"type": "object"}},
        output_required=("recommendation",),
        side_effects=("create_experiment_recommendation",),
        review_checklist=("Check recommendation rationale and risk class.",),
    ),
    "promotion.promote_lab": _tool(
        capability_name="promote_variant_lab",
        summary="Promote a variant into the lab progression path.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "variant_selection": {"type": "string"},
            "require_promote_decision": {"type": "boolean"},
        },
        output_properties={"variant_id": {"type": "string"}},
        output_required=("variant_id",),
        default_inputs={"variant_selection": "top_1", "require_promote_decision": True},
        side_effects=("create_analytics_event", "create_decision_event"),
        review_checklist=("Confirm the lab-promotion gate passed.",),
    ),
    "promotion.promote_prod": _tool(
        capability_name="promote_variant_prod",
        summary="Promote a variant toward production when readiness gates pass.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "variant_selection": {"type": "string"},
            "require_promote_decision": {"type": "boolean"},
        },
        output_properties={"variant_id": {"type": "string"}},
        output_required=("variant_id",),
        default_inputs={
            "variant_selection": "top_1",
            "require_promote_decision": True,
            "prod_min_coverage": 0.2,
            "min_verified_runs": 3,
            "min_synthetic_results": 1,
        },
        side_effects=("create_analytics_event", "create_decision_event"),
        review_checklist=("Confirm observed validation gates and rollback plan.",),
    ),
    "copy.publish_revision": _tool(
        capability_name="publish_copy_revision",
        summary="Publish an approved copy revision to the product description.",
        required_inputs=("experiment_id",),
        input_properties={
            "experiment_id": {"type": "string"},
            "variant_selection": {"type": "string"},
            "require_prod_promotion": {"type": "boolean"},
        },
        output_properties={"copy_revision_id": {"type": "string"}},
        output_required=("copy_revision_id",),
        default_inputs={"variant_selection": "top_1", "require_prod_promotion": True},
        side_effects=(
            "create_or_update_copy_revision",
            "update_product_description",
            "create_analytics_event",
            "create_decision_event",
        ),
        review_checklist=(
            "Confirm production promotion, copy diff, and manual rollback owner.",
        ),
    ),
}

_CAPABILITIES: Dict[str, CapabilitySpec] = {
    tool.capability_name: CapabilitySpec(
        name=tool.capability_name,
        tool_id=tool.id,
        summary=tool.summary,
        default_version=tool.default_version,
        required_inputs=tool.required_inputs,
        default_inputs=dict(tool.default_inputs),
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        side_effects=tool.side_effects,
        review_checklist=tool.review_checklist,
        owner_principal_id=tool.owner_principal_id,
        steward_team=tool.steward_team,
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


def default_tool_ownership_records() -> list[Dict[str, str]]:
    return [
        {
            "tool_id": tool.id,
            "owner_principal_id": tool.owner_principal_id,
            "steward_team": tool.steward_team,
        }
        for tool in list_tool_specs()
    ]


def list_policy_profiles() -> list[Dict[str, Any]]:
    return [
        {
            "id": "human_approval_required",
            "name": "Human Approval Required",
            "description": "Plan-first profile; proposed actions require operator approval before execution.",
            "auto_effect_classes": [],
        },
        {
            "id": "safe_auto",
            "name": "Safe Auto",
            "description": "Allows bounded execution for low-risk approved work while preserving gates for risky effects.",
            "auto_effect_classes": ["read", "recommend", "write_low_risk"],
        },
        {
            "id": "observe",
            "name": "Observe",
            "description": "Read-only profile for inspection, explanation, and audit workflows.",
            "auto_effect_classes": ["read", "recommend"],
        },
    ]


def policy_profile_supported(profile_id: str | None) -> bool:
    if not profile_id:
        return False
    return str(profile_id).strip().lower() in {
        profile["id"] for profile in list_policy_profiles()
    }


def run_mode_supported(run_mode: str | None) -> bool:
    return str(run_mode or "").strip().lower() in set(SUPPORTED_RUN_MODES)


def recovery_template_for_capability(capability_name: str) -> Dict[str, Any] | None:
    spec = get_capability_spec(capability_name)
    if not spec:
        return None
    default_inputs: Dict[str, Any] = {}
    summary = "Create a proposed recovery action using source-action context."
    operator_notes = [
        "Recovery proposals are created for operator review; they do not execute immediately.",
        "The source action id and failure context are attached in recovery_context.",
    ]
    if capability_name == "request_synthetic_validation":
        default_inputs["auto_run"] = False
        summary = (
            "Prepare validation recovery without auto-running external provider work."
        )
        operator_notes.append(
            "Keep auto_run disabled until duplicate provider/job risk has been reviewed."
        )
    elif capability_name == "review_validation_readiness":
        summary = (
            "Re-check readiness gates before creating more promotion or provider work."
        )
    elif capability_name == "recommend_next_action":
        summary = "Ask policy for the safest next recovery action."
    elif capability_name in {"promote_variant_lab", "promote_variant_prod"}:
        summary = "Recreate promotion as a proposed action after readiness review."
        operator_notes.append(
            "Confirm promotion evidence and rollback owner before approval."
        )
    elif capability_name == "publish_copy_revision":
        summary = (
            "Recreate publish as a proposed action after copy and rollback review."
        )
        operator_notes.append(
            "Confirm copy diff, prod promotion evidence, and rollback owner."
        )
    return {
        "id": f"recovery.{capability_name}",
        "capability_name": capability_name,
        "tool_id": spec.tool_id,
        "effect_class": spec.effect_class,
        "summary": summary,
        "default_inputs": default_inputs,
        "operator_notes": operator_notes,
        "side_effects": list(spec.side_effects),
    }


def list_recovery_templates() -> list[Dict[str, Any]]:
    return [
        template
        for capability in list_capability_specs()
        if (template := recovery_template_for_capability(capability.name)) is not None
    ]
