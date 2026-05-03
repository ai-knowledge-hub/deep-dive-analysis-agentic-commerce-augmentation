from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    list_skill_specs,
    tool_effect_class,
)

REGISTRY_VERSION = "agent-runtime-static-v1"


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
            properties={**_default_input_properties(defaults), **dict(input_properties or {})},
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
        output_required=("variant_id",),
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
        review_checklist=("Review generated copy and provenance before running variants.",),
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
        output_required=("variant_id",),
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
        review_checklist=("Inspect validation coverage and observed/synthetic agreement.",),
    ),
    "learning.update_posterior_and_decisions": _tool(
        capability_name="update_posterior_and_decisions",
        summary="Refresh posterior and decision outputs from latest evidence.",
        required_inputs=("experiment_id",),
        input_properties={"experiment_id": {"type": "string"}},
        output_properties={"metric_id": {"type": "string"}},
        side_effects=("create_experiment_metric", "create_decision_event"),
        review_checklist=("Review evidence freshness before treating decisions as final.",),
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
        review_checklist=("Confirm production promotion, copy diff, and manual rollback owner.",),
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


def registry_contract_payload(
    ownership_by_tool: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | None = None,
) -> Dict[str, Any]:
    ownership = _normalize_ownership_by_tool(ownership_by_tool)
    skills = [_serialize_spec(skill) for skill in list_skill_specs()]
    tools = [_serialize_tool(tool, ownership) for tool in list_tool_specs()]
    capabilities = [
        _serialize_capability(capability, ownership)
        for capability in list_capability_specs()
    ]
    skill_ids_by_tool: Dict[str, list[str]] = {}
    for skill in skills:
        for tool_id in skill.get("tool_ids", []) or []:
            skill_ids_by_tool.setdefault(str(tool_id), []).append(str(skill.get("id")))
    return {
        "registry_version": REGISTRY_VERSION,
        "registry_ownership_source": "persistent" if ownership else "static_code",
        "skills": skills,
        "tools": tools,
        "capabilities": capabilities,
        "skill_ids_by_tool": skill_ids_by_tool,
        "policy_profiles": list_policy_profiles(),
    }


def registry_fingerprint(
    ownership_by_tool: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | None = None,
) -> str:
    return _hash_payload(registry_contract_payload(ownership_by_tool=ownership_by_tool))


def _serialize_spec(value: Any) -> Dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return dict(getattr(value, "__dict__", {}))


def _serialize_tool(
    tool: ToolSpec, ownership_by_tool: Mapping[str, Mapping[str, Any]]
) -> Dict[str, Any]:
    payload = _serialize_spec(tool)
    ownership = ownership_by_tool.get(tool.id)
    if ownership:
        payload["owner_principal_id"] = str(
            ownership.get("owner_principal_id") or payload["owner_principal_id"]
        )
        payload["steward_team"] = str(
            ownership.get("steward_team") or payload["steward_team"]
        )
        payload["ownership_source"] = str(ownership.get("source") or "persistent")
    else:
        payload["ownership_source"] = "static_code"
    return payload


def _serialize_capability(
    capability: CapabilitySpec, ownership_by_tool: Mapping[str, Mapping[str, Any]]
) -> Dict[str, Any]:
    payload = _serialize_spec(capability)
    ownership = ownership_by_tool.get(capability.tool_id)
    if ownership:
        payload["owner_principal_id"] = str(
            ownership.get("owner_principal_id") or payload["owner_principal_id"]
        )
        payload["steward_team"] = str(
            ownership.get("steward_team") or payload["steward_team"]
        )
        payload["ownership_source"] = str(ownership.get("source") or "persistent")
    else:
        payload["ownership_source"] = "static_code"
    return payload


def _normalize_ownership_by_tool(
    ownership_by_tool: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | None,
) -> Dict[str, Dict[str, Any]]:
    if not ownership_by_tool:
        return {}
    if isinstance(ownership_by_tool, Mapping):
        return {
            str(tool_id): dict(value)
            for tool_id, value in ownership_by_tool.items()
            if isinstance(value, Mapping)
        }
    normalized: Dict[str, Dict[str, Any]] = {}
    for item in ownership_by_tool:
        if not isinstance(item, Mapping):
            continue
        tool_id = str(item.get("tool_id") or "").strip()
        if tool_id:
            normalized[tool_id] = dict(item)
    return normalized


def _hash_payload(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def version_context_for_capability(
    capability_name: str | None,
    *,
    tool_id: str | None = None,
    skill_id: str | None = None,
    registry_version_override: str | None = None,
    registry_fingerprint_override: str | None = None,
) -> Dict[str, str | None]:
    resolved_tool_id = str(tool_id or "").strip() or capability_to_tool_id(capability_name)
    spec = get_capability_spec(str(capability_name or ""))
    skill_version = None
    resolved_skill_id = str(skill_id or "").strip()
    for skill in list_skill_specs():
        if resolved_skill_id and skill.id == resolved_skill_id:
            skill_version = skill.version
            break
        if not resolved_skill_id and resolved_tool_id and resolved_tool_id in skill.tool_ids:
            skill_version = skill.version
            break
    return {
        "registry_version": registry_version_override or REGISTRY_VERSION,
        "registry_fingerprint": registry_fingerprint_override or registry_fingerprint(),
        "tool_version": spec.default_version if spec else None,
        "skill_version": skill_version,
    }


def next_state_for_capability(name: str) -> str | None:
    spec = get_capability_spec(name)
    return spec.next_state if spec else None


def validate_inputs(spec: CapabilitySpec, inputs: Mapping[str, Any]) -> list[str]:
    return _validate_mapping_schema(
        spec=spec,
        schema=spec.input_schema or {},
        values=inputs,
        value_label="Input",
    )


def validate_outputs(spec: CapabilitySpec, outputs: Mapping[str, Any]) -> list[str]:
    return _validate_mapping_schema(
        spec=spec,
        schema=spec.output_schema or {},
        values=outputs,
        value_label="Output",
    )


def _validate_mapping_schema(
    *,
    spec: CapabilitySpec,
    schema: Mapping[str, Any],
    values: Mapping[str, Any],
    value_label: str,
) -> list[str]:
    properties = schema.get("properties") if isinstance(schema, dict) else {}
    if not isinstance(properties, dict):
        return []
    errors: list[str] = []
    required = schema.get("required") if isinstance(schema, dict) else []
    if isinstance(required, list):
        for key in required:
            key_text = str(key)
            value = values.get(key_text)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(
                    f"{value_label} '{key_text}' for capability '{spec.name}' is required"
                )
    for key, definition in properties.items():
        if key not in values:
            continue
        if not isinstance(definition, dict):
            continue
        expected = definition.get("type")
        if not expected:
            continue
        value = values.get(key)
        if value is None:
            continue
        if not _matches_schema_type(value, str(expected)):
            errors.append(
                f"{value_label} '{key}' for capability '{spec.name}' must be {expected}"
            )
    return errors


def _matches_schema_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


__all__ = [
    "CapabilitySpec",
    "REGISTRY_VERSION",
    "ToolSpec",
    "default_tool_ownership_records",
    "get_tool_spec",
    "tool_supported",
    "list_tool_specs",
    "get_capability_spec",
    "capability_supported",
    "list_capability_specs",
    "list_policy_profiles",
    "next_state_for_capability",
    "registry_contract_payload",
    "registry_fingerprint",
    "validate_inputs",
    "validate_outputs",
    "version_context_for_capability",
]
