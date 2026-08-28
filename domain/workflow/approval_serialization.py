"""Canonical schema-v1 serialization for workflow approval envelopes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, TypeVar, cast

from domain.workflow.approval import (
    APPROVAL_ENVELOPE_CONTRACT,
    APPROVAL_ENVELOPE_SCHEMA_VERSION,
    ApprovalAuthority,
    ApprovalBinding,
    ApprovalContractError,
    ApprovalEnvelope,
    ApprovalStatus,
    EffectClass,
    NativeTargetIdentity,
    PrincipalType,
)


_EnumT = TypeVar("_EnumT", bound=Enum)

_TOP_LEVEL_KEYS = frozenset(
    {"contract", "schema_version", "approval_id", "scope", "lifecycle"}
)
_SCOPE_KEYS = frozenset(
    {
        "tenant_id",
        "principal_type",
        "principal_id",
        "workflow_id",
        "active_graph_revision",
        "task_id",
        "action_id",
        "capability_id",
        "tool_id",
        "effect_class",
        "native_target",
        "input_hash",
        "payload_hash",
        "evidence_digest",
        "authority_hash",
        "registry_version",
        "registry_fingerprint",
        "harness_id",
        "harness_version",
        "policy_profile_id",
        "policy_version",
        "effect_idempotency_key",
    }
)
_LIFECYCLE_KEYS = frozenset(
    {
        "status",
        "requested_at",
        "decided_at",
        "expires_at",
        "transitioned_at",
        "approving_authority",
        "revocation_reference",
        "supersession_reference",
        "fulfillment_receipt_id",
    }
)
_NATIVE_TARGET_KEYS = frozenset(
    {"provider_id", "resource_type", "resource_id", "parent_resource_id"}
)
_APPROVING_AUTHORITY_KEYS = frozenset(
    {"principal_type", "principal_id", "authority_source", "authority_version"}
)


def approval_envelope_payload(envelope: ApprovalEnvelope) -> dict[str, Any]:
    """Return the complete schema-v1 payload for an immutable snapshot."""

    binding = envelope.binding
    target = binding.native_target
    authority = envelope.approving_authority
    return {
        "contract": APPROVAL_ENVELOPE_CONTRACT,
        "schema_version": binding.schema_version,
        "approval_id": binding.approval_id,
        "scope": {
            "tenant_id": binding.tenant_id,
            "principal_type": binding.principal_type.value,
            "principal_id": binding.principal_id,
            "workflow_id": binding.workflow_id,
            "active_graph_revision": binding.active_graph_revision,
            "task_id": binding.task_id,
            "action_id": binding.action_id,
            "capability_id": binding.capability_id,
            "tool_id": binding.tool_id,
            "effect_class": binding.effect_class.value,
            "native_target": None
            if target is None
            else {
                "provider_id": target.provider_id,
                "resource_type": target.resource_type,
                "resource_id": target.resource_id,
                "parent_resource_id": target.parent_resource_id,
            },
            "input_hash": binding.input_hash,
            "payload_hash": binding.payload_hash,
            "evidence_digest": binding.evidence_digest,
            "authority_hash": binding.authority_hash,
            "registry_version": binding.registry_version,
            "registry_fingerprint": binding.registry_fingerprint,
            "harness_id": binding.harness_id,
            "harness_version": binding.harness_version,
            "policy_profile_id": binding.policy_profile_id,
            "policy_version": binding.policy_version,
            "effect_idempotency_key": binding.effect_idempotency_key,
        },
        "lifecycle": {
            "status": envelope.status.value,
            "requested_at": _format_datetime(binding.requested_at),
            "decided_at": _format_optional_datetime(envelope.decided_at),
            "expires_at": _format_datetime(binding.expires_at),
            "transitioned_at": _format_datetime(envelope.transitioned_at),
            "approving_authority": None
            if authority is None
            else {
                "principal_type": authority.principal_type.value,
                "principal_id": authority.principal_id,
                "authority_source": authority.authority_source,
                "authority_version": authority.authority_version,
            },
            "revocation_reference": envelope.revocation_reference,
            "supersession_reference": envelope.supersession_reference,
            "fulfillment_receipt_id": envelope.fulfillment_receipt_id,
        },
    }


def canonical_approval_envelope_bytes(envelope: ApprovalEnvelope) -> bytes:
    """Encode an envelope deterministically for hashing and persistence."""

    return json.dumps(
        approval_envelope_payload(envelope),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def approval_envelope_digest(envelope: ApprovalEnvelope) -> str:
    """Return the authorization fingerprint for this exact snapshot."""

    return hashlib.sha256(canonical_approval_envelope_bytes(envelope)).hexdigest()


def approval_envelope_from_payload(value: Mapping[str, Any]) -> ApprovalEnvelope:
    """Parse schema v1, rejecting omitted and unknown authority fields."""

    top_level = _as_mapping("approval envelope", value)
    _require_exact_keys("approval envelope", top_level, _TOP_LEVEL_KEYS)
    if top_level["contract"] != APPROVAL_ENVELOPE_CONTRACT:
        raise ApprovalContractError("unsupported approval envelope contract")
    if top_level["schema_version"] != APPROVAL_ENVELOPE_SCHEMA_VERSION:
        raise ApprovalContractError("unsupported approval envelope schema_version")

    scope = _as_mapping("scope", top_level["scope"])
    lifecycle = _as_mapping("lifecycle", top_level["lifecycle"])
    _require_exact_keys("scope", scope, _SCOPE_KEYS)
    _require_exact_keys("lifecycle", lifecycle, _LIFECYCLE_KEYS)

    binding = ApprovalBinding(
        approval_id=top_level["approval_id"],
        schema_version=top_level["schema_version"],
        tenant_id=scope["tenant_id"],
        principal_type=_parse_enum(PrincipalType, scope["principal_type"]),
        principal_id=scope["principal_id"],
        workflow_id=scope["workflow_id"],
        active_graph_revision=scope["active_graph_revision"],
        task_id=scope["task_id"],
        action_id=scope["action_id"],
        capability_id=scope["capability_id"],
        tool_id=scope["tool_id"],
        effect_class=_parse_enum(EffectClass, scope["effect_class"]),
        native_target=_parse_native_target(scope["native_target"]),
        input_hash=scope["input_hash"],
        payload_hash=scope["payload_hash"],
        evidence_digest=scope["evidence_digest"],
        authority_hash=scope["authority_hash"],
        registry_version=scope["registry_version"],
        registry_fingerprint=scope["registry_fingerprint"],
        harness_id=scope["harness_id"],
        harness_version=scope["harness_version"],
        policy_profile_id=scope["policy_profile_id"],
        policy_version=scope["policy_version"],
        effect_idempotency_key=scope["effect_idempotency_key"],
        requested_at=_parse_datetime("requested_at", lifecycle["requested_at"]),
        expires_at=_parse_datetime("expires_at", lifecycle["expires_at"]),
    )
    return ApprovalEnvelope(
        binding=binding,
        status=_parse_enum(ApprovalStatus, lifecycle["status"]),
        transitioned_at=_parse_datetime(
            "transitioned_at", lifecycle["transitioned_at"]
        ),
        decided_at=_parse_optional_datetime("decided_at", lifecycle["decided_at"]),
        approving_authority=_parse_approving_authority(
            lifecycle["approving_authority"]
        ),
        revocation_reference=lifecycle["revocation_reference"],
        supersession_reference=lifecycle["supersession_reference"],
        fulfillment_receipt_id=lifecycle["fulfillment_receipt_id"],
    )


def _format_datetime(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _format_optional_datetime(value: datetime | None) -> str | None:
    return None if value is None else _format_datetime(value)


def _parse_datetime(field_name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise ApprovalContractError(f"{field_name} must be a canonical timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApprovalContractError(
            f"{field_name} must be a canonical timestamp"
        ) from exc
    if parsed.utcoffset() is None or _format_datetime(parsed) != value:
        raise ApprovalContractError(f"{field_name} must use canonical UTC encoding")
    return parsed


def _parse_optional_datetime(field_name: str, value: object) -> datetime | None:
    return None if value is None else _parse_datetime(field_name, value)


def _as_mapping(field_name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ApprovalContractError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _require_exact_keys(
    field_name: str,
    value: Mapping[str, Any],
    expected: frozenset[str],
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ApprovalContractError(
            f"{field_name} fields must match schema v1; "
            f"missing={missing}, unknown={unknown}"
        )


def _parse_enum(enum_type: type[_EnumT], value: object) -> _EnumT:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ApprovalContractError(
            f"unsupported {enum_type.__name__} value {value!r}"
        ) from exc


def _parse_native_target(value: object) -> NativeTargetIdentity | None:
    if value is None:
        return None
    target = _as_mapping("native_target", value)
    _require_exact_keys("native_target", target, _NATIVE_TARGET_KEYS)
    return NativeTargetIdentity(
        provider_id=target["provider_id"],
        resource_type=target["resource_type"],
        resource_id=target["resource_id"],
        parent_resource_id=target["parent_resource_id"],
    )


def _parse_approving_authority(value: object) -> ApprovalAuthority | None:
    if value is None:
        return None
    authority = _as_mapping("approving_authority", value)
    _require_exact_keys("approving_authority", authority, _APPROVING_AUTHORITY_KEYS)
    return ApprovalAuthority(
        principal_type=_parse_enum(PrincipalType, authority["principal_type"]),
        principal_id=authority["principal_id"],
        authority_source=authority["authority_source"],
        authority_version=authority["authority_version"],
    )


__all__ = [
    "approval_envelope_digest",
    "approval_envelope_from_payload",
    "approval_envelope_payload",
    "canonical_approval_envelope_bytes",
]
