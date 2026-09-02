"""Canonical source snapshot for exact runtime approval revalidation."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


_RUN_FIELDS = (
    "id",
    "client_id",
    "principal_type",
    "principal_id",
    "allowed_capabilities",
    "budgets",
    "registry_version",
    "registry_fingerprint",
    "harness_id",
    "policy_profile_id",
    "active_graph_revision",
)

_ACTION_FIELDS = (
    "id",
    "agent_run_id",
    "capability_name",
    "capability_version",
    "tool_id",
    "tool_version",
    "effect_class",
    "inputs",
    "inputs_hash",
    "snapshot_version",
    "hypothesis_id",
    "variant_id",
    "validation_job_id",
    "rationale",
    "confidence",
    "registry_version",
    "registry_fingerprint",
    "dedupe_key",
)


def approval_execution_source_payload(
    *, run: Mapping[str, Any], action: Mapping[str, Any]
) -> dict[str, Any]:
    """Return every mutable source value used to rebuild an approval binding."""

    return {
        "contract": "workflow.approval-execution-source",
        "version": "1.0",
        "run": {field: run.get(field) for field in _RUN_FIELDS},
        "action": {field: action.get(field) for field in _ACTION_FIELDS},
    }


def approval_execution_source_digest(
    *, run: Mapping[str, Any], action: Mapping[str, Any]
) -> str:
    payload = approval_execution_source_payload(run=run, action=action)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def approval_effect_start_snapshot(
    *,
    approval_envelope: Mapping[str, Any],
    authorization_source_digest: str,
    executable_inputs: Mapping[str, Any],
    capability_contract_json: str,
    audit_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze every authority and payload needed to record a late receipt."""

    if type(capability_contract_json) is not str:
        raise TypeError("capability_contract_json must be exact text")
    capability_contract = json.loads(capability_contract_json)
    return json.loads(
        canonical_json(
            {
                "contract": "workflow.approval-effect-start",
                "version": "1.0",
                "approval_envelope": dict(approval_envelope),
                "authorization_source_digest": authorization_source_digest,
                "executable_inputs": dict(executable_inputs),
                "capability_contract": capability_contract,
                "audit_context": dict(audit_context),
            }
        )
    )


def approval_effect_start_snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = [
    "approval_effect_start_snapshot",
    "approval_effect_start_snapshot_digest",
    "approval_execution_source_digest",
    "approval_execution_source_payload",
    "canonical_json",
]
