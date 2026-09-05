"""Independent registry authority for exact action approvals."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from application.ports.deps import AppDeps
from application.services.agent_runtime.registry import (
    CapabilitySpec,
    registry_contract_payload,
)
from application.services.agent_runtime.registry.hashing import hash_registry_payload


class ApprovalRegistryError(ValueError):
    def __init__(self, message: str, *, mismatches: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.mismatches = mismatches


@dataclass(frozen=True)
class ApprovalRegistryAuthority:
    registry_version: str
    registry_fingerprint: str
    capability_id: str
    capability_version: str
    tool_id: str
    tool_version: str
    effect_class: str
    harness_id: str
    policy_profile_id: str
    capability_contract_json: str


def prepare_action_for_exact_approval(
    *,
    deps: AppDeps,
    run: Mapping[str, Any],
    action: Mapping[str, Any],
    spec: CapabilitySpec,
) -> tuple[dict[str, Any], ApprovalRegistryAuthority]:
    """Resolve identity from a versioned registry and normalize the sole payload."""

    payload, registry_version, fingerprint = _registry_payload(deps=deps, run=run)
    capability_name = _identifier("capability_name", action.get("capability_name"))
    capability = _find(payload.get("capabilities"), "name", capability_name)
    if capability is None:
        raise ApprovalRegistryError(
            "governed capability is absent from its pinned registry",
            mismatches=("capability_id",),
        )
    tool_id = _identifier("registry capability tool_id", capability.get("tool_id"))
    tool = _find(payload.get("tools"), "id", tool_id)
    if tool is None:
        raise ApprovalRegistryError(
            "governed tool is absent from its pinned registry",
            mismatches=("tool_id",),
        )
    capability_version = _identifier(
        "registry capability version", capability.get("default_version")
    )
    tool_version = _identifier("registry tool version", tool.get("default_version"))
    effect_class = _identifier(
        "registry capability effect_class", capability.get("effect_class")
    )
    harness_id = str(run.get("harness_id") or "operator_supervised").strip()
    policy_profile_id = str(
        run.get("policy_profile_id") or "human_approval_required"
    ).strip()
    if _find(payload.get("harness_profiles"), "id", harness_id) is None:
        raise ApprovalRegistryError(
            "workflow harness is absent from its pinned registry",
            mismatches=("harness_id",),
        )
    if _find(payload.get("policy_profiles"), "id", policy_profile_id) is None:
        raise ApprovalRegistryError(
            "workflow policy is absent from its pinned registry",
            mismatches=("policy_profile_id",),
        )
    capability_spec = _capability_spec(capability)
    authority = ApprovalRegistryAuthority(
        registry_version=registry_version,
        registry_fingerprint=fingerprint,
        capability_id=capability_name,
        capability_version=capability_version,
        tool_id=tool_id,
        tool_version=tool_version,
        effect_class=effect_class,
        harness_id=harness_id,
        policy_profile_id=policy_profile_id,
        capability_contract_json=_canonical_json(_executable_contract(capability_spec)),
    )
    mismatches = _identity_mismatches(
        run=run,
        action=action,
        spec=spec,
        authority=authority,
    )
    if mismatches:
        raise ApprovalRegistryError(
            "governed action identity does not match its versioned registry: "
            + ", ".join(mismatches),
            mismatches=mismatches,
        )
    normalized_inputs = capability_spec.normalize_inputs(action.get("inputs") or {})
    prepared = dict(action)
    prepared["inputs"] = normalized_inputs
    prepared["inputs_hash"] = _hash_payload(normalized_inputs)
    return prepared, authority


def _registry_payload(
    *, deps: AppDeps, run: Mapping[str, Any]
) -> tuple[dict[str, Any], str, str]:
    fingerprint = _digest("registry_fingerprint", run.get("registry_fingerprint"))
    registry_version = _identifier("registry_version", run.get("registry_version"))
    release = deps.agent_registry.get_agent_registry_version(
        registry_fingerprint=fingerprint
    )
    if release is None:
        payload = registry_contract_payload()
    else:
        payload = dict(release.get("payload") or {})
        if release.get("registry_version") != registry_version:
            raise ApprovalRegistryError(
                "workflow registry version does not match the durable registry record",
                mismatches=("registry_version",),
            )
    if hash_registry_payload(payload) != fingerprint:
        raise ApprovalRegistryError(
            "workflow registry fingerprint has no matching immutable registry payload",
            mismatches=("registry_fingerprint",),
        )
    if payload.get("registry_version") != registry_version:
        raise ApprovalRegistryError(
            "workflow registry version does not match its fingerprinted payload",
            mismatches=("registry_version",),
        )
    return payload, registry_version, fingerprint


def _identity_mismatches(
    *,
    run: Mapping[str, Any],
    action: Mapping[str, Any],
    spec: CapabilitySpec,
    authority: ApprovalRegistryAuthority,
) -> tuple[str, ...]:
    expected = {
        "capability_name": authority.capability_id,
        "capability_version": authority.capability_version,
        "tool_id": authority.tool_id,
        "tool_version": authority.tool_version,
        "effect_class": authority.effect_class,
        "registry_version": authority.registry_version,
        "registry_fingerprint": authority.registry_fingerprint,
    }
    mismatches = [
        field for field, value in expected.items() if action.get(field) != value
    ]
    if run.get("registry_version") != authority.registry_version:
        mismatches.append("run_registry_version")
    if run.get("registry_fingerprint") != authority.registry_fingerprint:
        mismatches.append("run_registry_fingerprint")
    supplied = {
        "capability_name": spec.name,
        "capability_version": spec.default_version,
        "tool_id": spec.tool_id,
        "effect_class": spec.effect_class,
    }
    for field, value in supplied.items():
        if value != expected[field]:
            mismatches.append(f"runtime_{field}")
    durable_contract = json.loads(authority.capability_contract_json)
    live_contract = json.loads(_canonical_json(_executable_contract(spec)))
    if live_contract != durable_contract:
        mismatches.append("runtime_executable_contract")
    return tuple(mismatches)


_CAPABILITY_CONTRACT_FIELDS = (
    "name",
    "tool_id",
    "summary",
    "default_version",
    "required_inputs",
    "default_inputs",
    "input_canonicalizers",
    "input_schema",
    "output_schema",
    "side_effects",
    "review_checklist",
    "owner_principal_id",
    "steward_team",
    "next_state",
    "effect_class",
)


def capability_spec_from_contract_json(contract_json: str) -> CapabilitySpec:
    """Rebuild the executable schema only from a frozen registry contract."""

    if type(contract_json) is not str:
        raise ApprovalRegistryError(
            "capability contract must be canonical JSON",
            mismatches=("capability_contract",),
        )
    try:
        payload = json.loads(contract_json)
    except (TypeError, ValueError) as exc:
        raise ApprovalRegistryError(
            "capability contract is not valid JSON",
            mismatches=("capability_contract",),
        ) from exc
    if type(payload) is not dict or _canonical_json(payload) != contract_json:
        raise ApprovalRegistryError(
            "capability contract is not canonical",
            mismatches=("capability_contract",),
        )
    return _capability_spec(payload)


def _capability_spec(payload: Mapping[str, Any]) -> CapabilitySpec:
    try:
        return CapabilitySpec(
            name=_identifier("capability name", payload.get("name")),
            tool_id=_identifier("capability tool_id", payload.get("tool_id")),
            summary=_exact_text("capability summary", payload.get("summary")),
            default_version=_identifier(
                "capability version", payload.get("default_version")
            ),
            required_inputs=_string_tuple(
                "capability required_inputs", payload.get("required_inputs")
            ),
            default_inputs=_mapping(
                "capability default_inputs", payload.get("default_inputs")
            ),
            input_canonicalizers=_string_mapping(
                "capability input_canonicalizers",
                payload.get("input_canonicalizers", {}),
            ),
            input_schema=_mapping(
                "capability input_schema", payload.get("input_schema")
            ),
            output_schema=_mapping(
                "capability output_schema", payload.get("output_schema")
            ),
            side_effects=_string_tuple(
                "capability side_effects", payload.get("side_effects")
            ),
            review_checklist=_string_tuple(
                "capability review_checklist", payload.get("review_checklist")
            ),
            owner_principal_id=_identifier(
                "capability owner_principal_id", payload.get("owner_principal_id")
            ),
            steward_team=_identifier(
                "capability steward_team", payload.get("steward_team")
            ),
            next_state=_optional_identifier(
                "capability next_state", payload.get("next_state")
            ),
            effect_class=_identifier(
                "capability effect_class", payload.get("effect_class")
            ),
        )
    except ApprovalRegistryError:
        raise
    except (TypeError, ValueError) as exc:
        raise ApprovalRegistryError(
            "versioned capability contract is malformed",
            mismatches=("capability_contract",),
        ) from exc


def _executable_contract(spec: CapabilitySpec) -> dict[str, Any]:
    return {field: getattr(spec, field) for field in _CAPABILITY_CONTRACT_FIELDS}


def _mapping(field_name: str, value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise ApprovalRegistryError(
            f"{field_name} must be an exact mapping", mismatches=(field_name,)
        )
    return json.loads(_canonical_json(value))


def _string_mapping(field_name: str, value: object) -> dict[str, str]:
    mapping = _mapping(field_name, value)
    return {
        _identifier(field_name, key): _identifier(field_name, item)
        for key, item in mapping.items()
    }


def _string_tuple(field_name: str, value: object) -> tuple[str, ...]:
    if type(value) not in {list, tuple}:
        raise ApprovalRegistryError(
            f"{field_name} must be a sequence", mismatches=(field_name,)
        )
    return tuple(_identifier(field_name, item) for item in value)


def _exact_text(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise ApprovalRegistryError(
            f"{field_name} must be exact text", mismatches=(field_name,)
        )
    return value


def _optional_identifier(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return _identifier(field_name, value)


def _find(values: object, field: str, expected: str) -> dict[str, Any] | None:
    if type(values) is not list:
        return None
    for value in values:
        if type(value) is dict and value.get(field) == expected:
            return dict(value)
    return None


def _identifier(field_name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ApprovalRegistryError(
            f"{field_name} must be a canonical identifier",
            mismatches=(field_name,),
        )
    return value


def _digest(field_name: str, value: object) -> str:
    normalized = _identifier(field_name, value)
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ApprovalRegistryError(
            f"{field_name} must be a lowercase SHA-256 digest",
            mismatches=(field_name,),
        )
    return normalized


def _hash_payload(value: object) -> str:
    encoded = _canonical_json(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = [
    "ApprovalRegistryAuthority",
    "ApprovalRegistryError",
    "capability_spec_from_contract_json",
    "prepare_action_for_exact_approval",
]
