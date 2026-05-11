from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Mapping, Sequence

from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    list_skill_specs,
    select_skill_for_tool_id,
    skill_specs_for_tool_id,
)
from application.services.agent_runtime.registry.catalog import (
    REGISTRY_VERSION,
    CapabilitySpec,
    ToolSpec,
    get_capability_spec,
    list_capability_specs,
    list_policy_profiles,
    list_recovery_templates,
    list_tool_specs,
)
from application.services.agent_runtime.registry.harnesses import list_harness_profiles


def registry_contract_payload(
    ownership_by_tool: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | None = None,
    harness_profiles: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    ownership = _normalize_ownership_by_tool(ownership_by_tool)
    skills = [_serialize_spec(skill) for skill in list_skill_specs()]
    tools = [_serialize_tool(tool, ownership) for tool in list_tool_specs()]
    capabilities = [
        _serialize_capability(capability, ownership)
        for capability in list_capability_specs()
    ]
    executable_tool_ids = {tool.id for tool in list_tool_specs()}
    skill_ids_by_tool: Dict[str, list[str]] = {}
    for skill in skills:
        for tool_id in skill.get("tool_ids", []) or []:
            skill_ids_by_tool.setdefault(str(tool_id), []).append(str(skill.get("id")))
    skill_tool_mappings = [
        {
            "tool_id": tool_id,
            "skill_ids": skill_ids,
            "executable": tool_id in executable_tool_ids,
        }
        for tool_id, skill_ids in sorted(skill_ids_by_tool.items())
    ]
    skill_ids_by_executable_tool = {
        item["tool_id"]: item["skill_ids"]
        for item in skill_tool_mappings
        if item["executable"]
    }
    declared_non_executable_skill_tools = [
        item["tool_id"] for item in skill_tool_mappings if not item["executable"]
    ]
    skill_selection_by_tool: Dict[str, Dict[str, Any]] = {}
    for tool_id in sorted(skill_ids_by_executable_tool):
        selected = select_skill_for_tool_id(tool_id)
        skill_selection_by_tool[tool_id] = {
            "default_skill_id": selected.id if selected else None,
            "candidate_skill_ids": [
                skill.id for skill in skill_specs_for_tool_id(tool_id)
            ],
        }
    return {
        "registry_version": REGISTRY_VERSION,
        "registry_ownership_source": "persistent" if ownership else "static_code",
        "skills": skills,
        "tools": tools,
        "capabilities": capabilities,
        "skill_ids_by_tool": skill_ids_by_tool,
        "skill_ids_by_executable_tool": skill_ids_by_executable_tool,
        "declared_non_executable_skill_tools": declared_non_executable_skill_tools,
        "skill_tool_mappings": skill_tool_mappings,
        "skill_selection_by_tool": skill_selection_by_tool,
        "recovery_templates": list_recovery_templates(),
        "policy_profiles": list_policy_profiles(),
        "harness_profiles": _normalize_harness_profiles(harness_profiles),
    }


def registry_fingerprint(
    ownership_by_tool: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | None = None,
    harness_profiles: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    return _hash_payload(
        registry_contract_payload(
            ownership_by_tool=ownership_by_tool,
            harness_profiles=harness_profiles,
        )
    )


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
    candidate_skill_ids = [skill.id for skill in skill_specs_for_tool_id(tool.id)]
    default_skill = select_skill_for_tool_id(tool.id)
    payload["executable"] = True
    payload["external_agent_contract"] = {
        "job_endpoint": "POST /external-agent/jobs",
        "accepted_plan_modes": ["single_tool", "workflow"],
        "required_scopes": {
            "tool": [f"tool:{tool.id}", "tools:*"],
            "skill": [f"skill:{skill_id}" for skill_id in candidate_skill_ids]
            + ["skills:*"],
        },
        "default_skill_id": default_skill.id if default_skill else None,
        "candidate_skill_ids": candidate_skill_ids,
        "minimal_request": {
            "tool_id": tool.id,
            "plan_mode": "single_tool",
        },
    }
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
    candidate_skill_ids = [skill.id for skill in skill_specs_for_tool_id(capability.tool_id)]
    default_skill = select_skill_for_tool_id(capability.tool_id)
    payload["executable"] = True
    payload["external_agent_contract"] = {
        "job_endpoint": "POST /external-agent/jobs",
        "accepted_plan_modes": ["single_tool", "workflow"],
        "required_scopes": {
            "tool": [f"tool:{capability.tool_id}", "tools:*"],
            "skill": [f"skill:{skill_id}" for skill_id in candidate_skill_ids]
            + ["skills:*"],
        },
        "default_skill_id": default_skill.id if default_skill else None,
        "candidate_skill_ids": candidate_skill_ids,
        "minimal_request": {
            "capability_name": capability.name,
            "plan_mode": "single_tool",
        },
    }
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


def _normalize_harness_profiles(
    harness_profiles: Sequence[Mapping[str, Any]] | None,
) -> list[Dict[str, Any]]:
    profiles = harness_profiles if harness_profiles is not None else list_harness_profiles()
    normalized = []
    for profile in profiles:
        item = dict(profile)
        item.pop("created_at", None)
        item.pop("updated_at", None)
        normalized.append(item)
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
    resolved_tool_id = str(tool_id or "").strip() or capability_to_tool_id(
        capability_name
    )
    spec = get_capability_spec(str(capability_name or ""))
    skill_version = None
    resolved_skill_id = str(skill_id or "").strip()
    for skill in list_skill_specs():
        if resolved_skill_id and skill.id == resolved_skill_id:
            skill_version = skill.version
            break
        if (
            not resolved_skill_id
            and resolved_tool_id
            and resolved_tool_id in skill.tool_ids
        ):
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
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(
            value, bool
        )
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True
