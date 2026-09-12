"""Canonical host-only serialization for completion authority snapshots.

Unlike worker-submitted evidence and results, this representation is issued from
host-owned state. It exists so the authority oracle can survive process restarts;
it is not an input contract for workers or external callers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final, cast

from domain.workflow.outcomes import (
    OUTCOME_SCHEMA_VERSION,
    AcceptedTaskResultAttestation,
    AuthoritativeTaskDefinition,
    CompletionAuthoritySnapshot,
    ContractAuthority,
    OutcomeContractError,
    ResultValidationAuthority,
)


COMPLETION_AUTHORITY_SNAPSHOT_CONTRACT: Final = "workflow.completion-authority-snapshot"


def completion_authority_snapshot_payload(
    value: CompletionAuthoritySnapshot,
) -> dict[str, Any]:
    """Return the unique durable representation of a host-issued snapshot."""

    if type(value) is not CompletionAuthoritySnapshot:
        raise OutcomeContractError(
            "authority snapshot must be exact CompletionAuthoritySnapshot"
        )
    value.validate()
    return {
        "contract": COMPLETION_AUTHORITY_SNAPSHOT_CONTRACT,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "scope": {
            "tenant_id": value.tenant_id,
            "workflow_id": value.workflow_id,
            "graph_revision": value.graph_revision,
            "objective_id": value.objective_id,
        },
        "criteria_id": value.criteria_id,
        "criteria_hash": value.criteria_hash,
        "criteria_authority_hash": value.criteria_authority_hash,
        "publishing_authority": _contract_authority_payload(value.publishing_authority),
        "evaluation_authority": _contract_authority_payload(value.evaluation_authority),
        "task_definitions": [
            {
                "task_id": item.task_id,
                "task_input_hash": item.task_input_hash,
                "result_schema_id": item.result_schema_id,
                "result_schema_version": item.result_schema_version,
                "result_schema_hash": item.result_schema_hash,
            }
            for item in value.task_definitions
        ],
        "accepted_result_attestations": [
            {
                "task_id": item.task_id,
                "attempt_id": item.attempt_id,
                "assignment_id": item.assignment_id,
                "validation_authority": _result_authority_payload(
                    item.validation_authority
                ),
                "accepted_result_hash": item.accepted_result_hash,
            }
            for item in value.accepted_result_attestations
        ],
    }


def completion_authority_snapshot_from_payload(
    value: dict[str, Any],
) -> CompletionAuthoritySnapshot:
    """Reconstruct a snapshot read from the trusted durable ledger."""

    top = _mapping("authority snapshot", value)
    _keys(
        "authority snapshot",
        top,
        {
            "contract",
            "schema_version",
            "scope",
            "criteria_id",
            "criteria_hash",
            "criteria_authority_hash",
            "publishing_authority",
            "evaluation_authority",
            "task_definitions",
            "accepted_result_attestations",
        },
    )
    if (
        type(top["contract"]) is not str
        or top["contract"] != COMPLETION_AUTHORITY_SNAPSHOT_CONTRACT
    ):
        raise OutcomeContractError("unsupported completion authority contract")
    if (
        type(top["schema_version"]) is not str
        or top["schema_version"] != OUTCOME_SCHEMA_VERSION
    ):
        raise OutcomeContractError("unsupported completion authority schema_version")
    scope = _mapping("scope", top["scope"])
    _keys(
        "scope",
        scope,
        {"tenant_id", "workflow_id", "graph_revision", "objective_id"},
    )
    definitions: list[AuthoritativeTaskDefinition] = []
    for raw in _list("task_definitions", top["task_definitions"]):
        item = _mapping("task definition", raw)
        _keys(
            "task definition",
            item,
            {
                "task_id",
                "task_input_hash",
                "result_schema_id",
                "result_schema_version",
                "result_schema_hash",
            },
        )
        definitions.append(AuthoritativeTaskDefinition(**item))
    attestations: list[AcceptedTaskResultAttestation] = []
    for raw in _list(
        "accepted_result_attestations", top["accepted_result_attestations"]
    ):
        item = _mapping("accepted result attestation", raw)
        _keys(
            "accepted result attestation",
            item,
            {
                "task_id",
                "attempt_id",
                "assignment_id",
                "validation_authority",
                "accepted_result_hash",
            },
        )
        attestations.append(
            AcceptedTaskResultAttestation(
                task_id=item["task_id"],
                attempt_id=item["attempt_id"],
                assignment_id=item["assignment_id"],
                validation_authority=_result_authority_from_payload(
                    item["validation_authority"]
                ),
                accepted_result_hash=item["accepted_result_hash"],
            )
        )
    return CompletionAuthoritySnapshot(
        tenant_id=scope["tenant_id"],
        workflow_id=scope["workflow_id"],
        graph_revision=scope["graph_revision"],
        objective_id=scope["objective_id"],
        criteria_id=top["criteria_id"],
        criteria_hash=top["criteria_hash"],
        criteria_authority_hash=top["criteria_authority_hash"],
        publishing_authority=_contract_authority_from_payload(
            top["publishing_authority"]
        ),
        evaluation_authority=_contract_authority_from_payload(
            top["evaluation_authority"]
        ),
        task_definitions=tuple(definitions),
        accepted_result_attestations=tuple(attestations),
    )


def completion_authority_snapshot_digest(
    value: CompletionAuthoritySnapshot,
) -> str:
    payload = completion_authority_snapshot_payload(value)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _contract_authority_payload(value: ContractAuthority) -> dict[str, str]:
    return {
        "principal_id": value.principal_id,
        "authority_source": value.authority_source,
        "authority_version": value.authority_version,
    }


def _result_authority_payload(
    value: ResultValidationAuthority,
) -> dict[str, str]:
    return {
        "principal_id": value.principal_id,
        "authority_source": value.authority_source,
        "authority_version": value.authority_version,
    }


def _contract_authority_from_payload(value: object) -> ContractAuthority:
    authority = _authority_mapping("contract authority", value)
    return ContractAuthority(**authority)


def _result_authority_from_payload(value: object) -> ResultValidationAuthority:
    authority = _authority_mapping("result validation authority", value)
    return ResultValidationAuthority(**authority)


def _authority_mapping(field_name: str, value: object) -> dict[str, str]:
    authority = _mapping(field_name, value)
    _keys(
        field_name,
        authority,
        {"principal_id", "authority_source", "authority_version"},
    )
    if any(type(item) is not str for item in authority.values()):
        raise OutcomeContractError(f"{field_name} values must be exact strings")
    return cast(dict[str, str], authority)


def _mapping(field_name: str, value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise OutcomeContractError(f"{field_name} must be an exact object")
    return cast(dict[str, Any], value)


def _list(field_name: str, value: object) -> list[Any]:
    if type(value) is not list:
        raise OutcomeContractError(f"{field_name} must be an exact array")
    return cast(list[Any], value)


def _keys(field_name: str, value: dict[str, Any], expected: set[str]) -> None:
    if any(type(key) is not str for key in value):
        raise OutcomeContractError(f"{field_name} keys must be exact strings")
    actual = set(value)
    if actual != expected:
        raise OutcomeContractError(
            f"{field_name} fields must match schema v1; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


__all__ = [
    "COMPLETION_AUTHORITY_SNAPSHOT_CONTRACT",
    "completion_authority_snapshot_digest",
    "completion_authority_snapshot_from_payload",
    "completion_authority_snapshot_payload",
]
