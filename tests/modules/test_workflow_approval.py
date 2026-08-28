from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

import pytest

from domain.workflow import (
    APPROVAL_ENVELOPE_CONTRACT,
    APPROVAL_ENVELOPE_SCHEMA_VERSION,
    TERMINAL_APPROVAL_STATUSES,
    ApprovalAuthority,
    ApprovalBinding,
    ApprovalContractError,
    ApprovalEnvelope,
    ApprovalStatus,
    ApprovalTransition,
    ApprovalTransitionError,
    EffectClass,
    NativeTargetIdentity,
    PrincipalType,
    allowed_approval_transitions,
    approval_envelope_digest,
    approval_envelope_from_payload,
    approval_envelope_payload,
    approval_status_from_legacy_action_status,
    can_transition_approval,
    canonical_approval_envelope_bytes,
    create_approval_request,
    require_approval_transition,
    transition_approval,
)


REQUESTED_AT = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)
EXPIRES_AT = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
DECIDED_AT = datetime(2026, 8, 25, 9, 5, tzinfo=timezone.utc)

EXPECTED_TRANSITIONS = {
    ApprovalStatus.REQUESTED: {
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.SUPERSEDED,
    },
    ApprovalStatus.APPROVED: {
        ApprovalStatus.EXPIRED,
        ApprovalStatus.REVOKED,
        ApprovalStatus.SUPERSEDED,
        ApprovalStatus.FULFILLED,
    },
    ApprovalStatus.REJECTED: set(),
    ApprovalStatus.EXPIRED: set(),
    ApprovalStatus.REVOKED: set(),
    ApprovalStatus.SUPERSEDED: set(),
    ApprovalStatus.FULFILLED: set(),
}


def make_binding(**overrides: Any) -> ApprovalBinding:
    values: dict[str, Any] = {
        "approval_id": "approval-001",
        "schema_version": APPROVAL_ENVELOPE_SCHEMA_VERSION,
        "tenant_id": "tenant-001",
        "principal_type": PrincipalType.INTERNAL_AGENT,
        "principal_id": "agent-001",
        "workflow_id": "workflow-001",
        "active_graph_revision": 3,
        "task_id": "task-001",
        "action_id": "action-001",
        "capability_id": "publish_copy_revision",
        "tool_id": "commerce.publish_copy_revision",
        "effect_class": EffectClass.WRITE_HIGH_RISK,
        "native_target": NativeTargetIdentity(
            provider_id="shopify",
            resource_type="product",
            resource_id="gid://shopify/Product/123",
            parent_resource_id="gid://shopify/Shop/456",
        ),
        "input_hash": "a" * 64,
        "payload_hash": "b" * 64,
        "evidence_digest": "c" * 64,
        "authority_hash": "d" * 64,
        "registry_version": "registry-v4",
        "registry_fingerprint": "e" * 64,
        "harness_id": "commerce-harness",
        "harness_version": "harness-v7",
        "policy_profile_id": "beta-effects",
        "policy_version": "policy-v3",
        "effect_idempotency_key": "effect-001",
        "requested_at": REQUESTED_AT,
        "expires_at": EXPIRES_AT,
    }
    values.update(overrides)
    return ApprovalBinding(**values)


def make_authority(**overrides: Any) -> ApprovalAuthority:
    values: dict[str, Any] = {
        "principal_type": PrincipalType.HUMAN,
        "principal_id": "operator-001",
        "authority_source": "operator-policy",
        "authority_version": "operator-policy-v2",
    }
    values.update(overrides)
    return ApprovalAuthority(**values)


def make_requested(**binding_overrides: Any) -> ApprovalEnvelope:
    return create_approval_request(make_binding(**binding_overrides))


def make_approved() -> ApprovalEnvelope:
    return transition_approval(
        make_requested(),
        ApprovalStatus.APPROVED,
        occurred_at=DECIDED_AT,
        approving_authority=make_authority(),
    )


@pytest.mark.parametrize("source", list(ApprovalStatus))
def test_allowed_transitions_match_complete_contract(source: ApprovalStatus) -> None:
    assert allowed_approval_transitions(source) == EXPECTED_TRANSITIONS[source]


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (source, target)
        for source in ApprovalStatus
        for target in ApprovalStatus
        if target in EXPECTED_TRANSITIONS[source]
    ],
)
def test_every_declared_transition_is_executable(
    source: ApprovalStatus,
    target: ApprovalStatus,
) -> None:
    assert can_transition_approval(source, target)
    assert require_approval_transition(source, target) == ApprovalTransition(
        source, target
    )


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (source, target)
        for source in ApprovalStatus
        for target in ApprovalStatus
        if target not in EXPECTED_TRANSITIONS[source]
    ],
)
def test_every_undeclared_transition_is_rejected(
    source: ApprovalStatus,
    target: ApprovalStatus,
) -> None:
    assert not can_transition_approval(source, target)
    with pytest.raises(ApprovalTransitionError) as error:
        require_approval_transition(source, target)
    assert error.value.source is source
    assert error.value.target is target


def test_terminal_statuses_are_explicit_and_absorbing() -> None:
    assert TERMINAL_APPROVAL_STATUSES == {
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.REVOKED,
        ApprovalStatus.SUPERSEDED,
        ApprovalStatus.FULFILLED,
    }
    assert all(
        not allowed_approval_transitions(status)
        for status in TERMINAL_APPROVAL_STATUSES
    )


def test_request_is_an_immutable_snapshot_at_requested_time() -> None:
    request = make_requested()

    assert request.status is ApprovalStatus.REQUESTED
    assert request.transitioned_at == REQUESTED_AT
    with pytest.raises(FrozenInstanceError):
        request.status = ApprovalStatus.APPROVED  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        request.binding.workflow_id = "different"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("source_factory", "target", "occurred_at", "metadata"),
    [
        (make_requested, ApprovalStatus.REJECTED, DECIDED_AT, {"authority": True}),
        (make_requested, ApprovalStatus.EXPIRED, EXPIRES_AT, {}),
        (
            make_requested,
            ApprovalStatus.SUPERSEDED,
            DECIDED_AT,
            {"supersession_reference": "approval-002"},
        ),
        (
            make_approved,
            ApprovalStatus.REVOKED,
            DECIDED_AT + timedelta(minutes=1),
            {"revocation_reference": "incident-001"},
        ),
        (
            make_approved,
            ApprovalStatus.SUPERSEDED,
            DECIDED_AT + timedelta(minutes=1),
            {"supersession_reference": "approval-002"},
        ),
        (make_approved, ApprovalStatus.EXPIRED, EXPIRES_AT, {}),
        (
            make_approved,
            ApprovalStatus.FULFILLED,
            DECIDED_AT + timedelta(minutes=1),
            {"fulfillment_receipt_id": "receipt-001"},
        ),
    ],
)
def test_valid_lifecycle_transitions_preserve_the_binding(
    source_factory: Callable[[], ApprovalEnvelope],
    target: ApprovalStatus,
    occurred_at: datetime,
    metadata: dict[str, Any],
) -> None:
    source = source_factory()
    authority = make_authority() if metadata.pop("authority", False) else None

    result = transition_approval(
        source,
        target,
        occurred_at=occurred_at,
        approving_authority=authority,
        **metadata,
    )

    assert result.status is target
    assert result.binding is source.binding


@pytest.mark.parametrize("target", [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED])
def test_decisions_require_an_authoritative_principal(target: ApprovalStatus) -> None:
    with pytest.raises(ApprovalContractError, match="approving_authority"):
        transition_approval(make_requested(), target, occurred_at=DECIDED_AT)


@pytest.mark.parametrize(
    ("target", "metadata"),
    [
        (ApprovalStatus.REVOKED, {}),
        (ApprovalStatus.SUPERSEDED, {}),
        (ApprovalStatus.FULFILLED, {}),
        (
            ApprovalStatus.REVOKED,
            {"supersession_reference": "approval-002"},
        ),
        (
            ApprovalStatus.SUPERSEDED,
            {"fulfillment_receipt_id": "receipt-001"},
        ),
    ],
)
def test_effect_ending_transitions_require_only_their_own_reference(
    target: ApprovalStatus,
    metadata: dict[str, str],
) -> None:
    with pytest.raises(ApprovalContractError):
        transition_approval(
            make_approved(),
            target,
            occurred_at=DECIDED_AT + timedelta(minutes=1),
            **metadata,
        )


def test_time_cannot_move_backwards_or_authorize_at_expiry() -> None:
    approved = make_approved()
    with pytest.raises(ApprovalContractError, match="backwards"):
        transition_approval(
            approved,
            ApprovalStatus.REVOKED,
            occurred_at=REQUESTED_AT,
            revocation_reference="incident-001",
        )
    with pytest.raises(ApprovalContractError, match="after approval expiry"):
        transition_approval(
            make_requested(),
            ApprovalStatus.APPROVED,
            occurred_at=EXPIRES_AT,
            approving_authority=make_authority(),
        )
    with pytest.raises(ApprovalContractError, match="before expires_at"):
        transition_approval(
            make_requested(),
            ApprovalStatus.EXPIRED,
            occurred_at=DECIDED_AT,
        )


def test_late_fulfillment_records_outcome_but_does_not_authorize_new_work() -> None:
    fulfilled = transition_approval(
        make_approved(),
        ApprovalStatus.FULFILLED,
        occurred_at=EXPIRES_AT + timedelta(minutes=5),
        fulfillment_receipt_id="receipt-after-timeout",
    )

    assert fulfilled.status is ApprovalStatus.FULFILLED
    assert fulfilled.transitioned_at > fulfilled.binding.expires_at
    with pytest.raises(ApprovalContractError, match="after approval expiry"):
        transition_approval(
            make_approved(),
            ApprovalStatus.REVOKED,
            occurred_at=EXPIRES_AT,
            revocation_reference="late-revocation",
        )


@pytest.mark.parametrize(
    ("status", "reference_field"),
    [
        (ApprovalStatus.REVOKED, "revocation_reference"),
        (ApprovalStatus.SUPERSEDED, "supersession_reference"),
    ],
)
def test_direct_or_parsed_snapshot_cannot_bypass_expiry_rules(
    status: ApprovalStatus,
    reference_field: str,
) -> None:
    approved = make_approved()
    values = {
        "binding": approved.binding,
        "status": status,
        "transitioned_at": EXPIRES_AT,
        "decided_at": approved.decided_at,
        "approving_authority": approved.approving_authority,
        reference_field: "terminal-reference",
    }

    with pytest.raises(ApprovalContractError, match="after approval expiry"):
        ApprovalEnvelope(**values)


@pytest.mark.parametrize("field_name", ["requested_at", "expires_at"])
def test_binding_timestamps_must_be_timezone_aware(field_name: str) -> None:
    with pytest.raises(ApprovalContractError, match="timezone-aware"):
        make_binding(**{field_name: datetime(2026, 8, 25, 9, 0)})


def test_expiry_must_follow_request() -> None:
    with pytest.raises(ApprovalContractError, match="after requested_at"):
        make_binding(expires_at=REQUESTED_AT)


class ImpostorEnum(str, Enum):
    HUMAN = "human"
    APPROVED = "approved"


@pytest.mark.parametrize(
    ("factory", "overrides"),
    [
        (make_binding, {"principal_type": ImpostorEnum.HUMAN}),
        (make_binding, {"effect_class": ImpostorEnum.APPROVED}),
        (make_authority, {"principal_type": ImpostorEnum.HUMAN}),
    ],
)
def test_same_value_from_a_different_enum_cannot_impersonate_contract_type(
    factory: Callable[..., object],
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ApprovalContractError, match="supported enum"):
        factory(**overrides)


def test_parser_round_trips_the_complete_envelope() -> None:
    approved = make_approved()
    payload = approval_envelope_payload(approved)

    assert approval_envelope_from_payload(payload) == approved
    assert payload["contract"] == APPROVAL_ENVELOPE_CONTRACT


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("scope",),
        ("lifecycle",),
        ("scope", "native_target"),
        ("lifecycle", "approving_authority"),
    ],
)
@pytest.mark.parametrize("mutation", ["omit", "unknown"])
def test_parser_rejects_missing_or_unknown_fields_at_every_schema_level(
    path: tuple[str, ...],
    mutation: str,
) -> None:
    payload = copy.deepcopy(approval_envelope_payload(make_approved()))
    target: dict[str, Any] = payload
    for segment in path:
        target = target[segment]
    if mutation == "omit":
        target.pop(next(iter(target)))
    else:
        target["future_authority_field"] = "fail-closed"

    with pytest.raises(ApprovalContractError, match="fields must match schema v1"):
        approval_envelope_from_payload(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("contract",), "different.contract"),
        (("schema_version",), "2.0"),
        (("scope", "principal_type"), "service"),
        (("scope", "effect_class"), "unknown"),
        (("lifecycle", "status"), "pending"),
        (("lifecycle", "requested_at"), "2026-08-25T09:00:00Z"),
        (("lifecycle", "expires_at"), "2026-08-25T11:00:00.000000+01:00"),
    ],
)
def test_parser_rejects_unsupported_or_noncanonical_values(
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = copy.deepcopy(approval_envelope_payload(make_approved()))
    target: dict[str, Any] = payload
    for segment in path[:-1]:
        target = target[segment]
    target[path[-1]] = value

    with pytest.raises(ApprovalContractError):
        approval_envelope_from_payload(payload)


def test_canonical_serialization_and_digest_are_stable() -> None:
    approved = make_approved()

    assert canonical_approval_envelope_bytes(approved).startswith(
        b'{"approval_id":"approval-001","contract":"workflow.approval-envelope"'
    )
    assert approval_envelope_digest(approved) == (
        "a92d22a991500cbdb8719c0efa8562f41c8a50fdff95faa211d89f7c629bdbbd"
    )


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("approval_id", "approval-002"),
        ("tenant_id", "tenant-002"),
        ("principal_type", PrincipalType.EXTERNAL_AGENT),
        ("principal_id", "agent-002"),
        ("workflow_id", "workflow-002"),
        ("active_graph_revision", 4),
        ("task_id", "task-002"),
        ("action_id", "action-002"),
        ("capability_id", "promote_variant_prod"),
        ("tool_id", "commerce.promote_variant_prod"),
        ("effect_class", EffectClass.EXTERNAL_SIDE_EFFECT),
        ("native_target", None),
        ("input_hash", "1" * 64),
        ("payload_hash", "2" * 64),
        ("evidence_digest", "3" * 64),
        ("authority_hash", "4" * 64),
        ("registry_version", "registry-v5"),
        ("registry_fingerprint", "5" * 64),
        ("harness_id", "different-harness"),
        ("harness_version", "harness-v8"),
        ("policy_profile_id", "different-policy"),
        ("policy_version", "policy-v4"),
        ("effect_idempotency_key", "effect-002"),
        ("requested_at", REQUESTED_AT - timedelta(minutes=1)),
        ("expires_at", EXPIRES_AT + timedelta(minutes=1)),
    ],
)
def test_every_binding_dimension_changes_the_authorization_fingerprint(
    field_name: str,
    new_value: object,
) -> None:
    original = make_requested()
    mutated = create_approval_request(
        replace(original.binding, **{field_name: new_value})
    )

    assert approval_envelope_digest(mutated) != approval_envelope_digest(original)


def test_timezone_equivalent_instants_have_the_same_fingerprint() -> None:
    offset = timezone(timedelta(hours=1))
    original = make_requested()
    equivalent = create_approval_request(
        replace(
            original.binding,
            requested_at=REQUESTED_AT.astimezone(offset),
            expires_at=EXPIRES_AT.astimezone(offset),
        )
    )

    assert approval_envelope_digest(equivalent) == approval_envelope_digest(original)


def test_decision_and_terminal_evidence_change_the_snapshot_fingerprint() -> None:
    requested = make_requested()
    approved = make_approved()
    fulfilled = transition_approval(
        approved,
        ApprovalStatus.FULFILLED,
        occurred_at=DECIDED_AT + timedelta(minutes=1),
        fulfillment_receipt_id="receipt-001",
    )

    assert (
        len(
            {
                approval_envelope_digest(requested),
                approval_envelope_digest(approved),
                approval_envelope_digest(fulfilled),
            }
        )
        == 3
    )


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("provider_id", "google-merchant-center"),
        ("resource_type", "campaign"),
        ("resource_id", "campaign-002"),
        ("parent_resource_id", None),
    ],
)
def test_each_native_target_dimension_changes_the_fingerprint(
    field_name: str,
    new_value: str | None,
) -> None:
    original = make_approved()
    target = original.binding.native_target
    assert target is not None
    mutated = replace(
        original,
        binding=replace(
            original.binding,
            native_target=replace(target, **{field_name: new_value}),
        ),
    )

    assert approval_envelope_digest(mutated) != approval_envelope_digest(original)


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("principal_type", PrincipalType.INTERNAL_AGENT),
        ("principal_id", "operator-002"),
        ("authority_source", "break-glass-policy"),
        ("authority_version", "operator-policy-v3"),
    ],
)
def test_each_decision_authority_dimension_changes_the_fingerprint(
    field_name: str,
    new_value: object,
) -> None:
    original = make_approved()
    authority = original.approving_authority
    assert authority is not None
    mutated = replace(
        original,
        approving_authority=replace(authority, **{field_name: new_value}),
    )

    assert approval_envelope_digest(mutated) != approval_envelope_digest(original)


@pytest.mark.parametrize(
    ("legacy_status", "expected"),
    [
        ("approved", ApprovalStatus.APPROVED),
        (" APPROVED ", ApprovalStatus.APPROVED),
        ("rejected", ApprovalStatus.REJECTED),
        ("executed", None),
        ("failed", None),
        ("proposed", None),
        ("", None),
        (None, None),
    ],
)
def test_legacy_action_status_is_only_a_decision_projection(
    legacy_status: str | None,
    expected: ApprovalStatus | None,
) -> None:
    assert approval_status_from_legacy_action_status(legacy_status) is expected


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("approval_id", " "),
        ("tenant_id", " tenant-001"),
        ("workflow_id", ""),
        ("active_graph_revision", True),
        ("active_graph_revision", 0),
        ("input_hash", "A" * 64),
        ("payload_hash", "short"),
        ("registry_fingerprint", "g" * 64),
        ("schema_version", "2.0"),
    ],
)
def test_invalid_binding_values_fail_closed(field_name: str, bad_value: object) -> None:
    with pytest.raises(ApprovalContractError):
        make_binding(**{field_name: bad_value})
