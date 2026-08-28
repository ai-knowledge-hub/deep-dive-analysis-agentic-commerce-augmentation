"""Pure approval authority and lifecycle contracts for governed effects."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping


APPROVAL_ENVELOPE_CONTRACT: Final = "workflow.approval-envelope"
APPROVAL_ENVELOPE_SCHEMA_VERSION: Final = "1.0"


class PrincipalType(str, Enum):
    HUMAN = "human"
    INTERNAL_AGENT = "internal_agent"
    EXTERNAL_AGENT = "external_agent"


class EffectClass(str, Enum):
    READ = "read"
    RECOMMEND = "recommend"
    WRITE_LOW_RISK = "write_low_risk"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    WRITE_HIGH_RISK = "write_high_risk"


class ApprovalStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"
    FULFILLED = "fulfilled"


TERMINAL_APPROVAL_STATUSES: Final[frozenset[ApprovalStatus]] = frozenset(
    {
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.REVOKED,
        ApprovalStatus.SUPERSEDED,
        ApprovalStatus.FULFILLED,
    }
)

_ALLOWED_APPROVAL_TRANSITIONS: Final[
    Mapping[ApprovalStatus, frozenset[ApprovalStatus]]
] = MappingProxyType(
    {
        ApprovalStatus.REQUESTED: frozenset(
            {
                ApprovalStatus.APPROVED,
                ApprovalStatus.REJECTED,
                ApprovalStatus.EXPIRED,
                ApprovalStatus.SUPERSEDED,
            }
        ),
        ApprovalStatus.APPROVED: frozenset(
            {
                ApprovalStatus.EXPIRED,
                ApprovalStatus.REVOKED,
                ApprovalStatus.SUPERSEDED,
                ApprovalStatus.FULFILLED,
            }
        ),
        ApprovalStatus.REJECTED: frozenset(),
        ApprovalStatus.EXPIRED: frozenset(),
        ApprovalStatus.REVOKED: frozenset(),
        ApprovalStatus.SUPERSEDED: frozenset(),
        ApprovalStatus.FULFILLED: frozenset(),
    }
)

_LEGACY_ACTION_DECISION_STATUSES: Final[Mapping[str, ApprovalStatus]] = (
    MappingProxyType(
        {
            "approved": ApprovalStatus.APPROVED,
            "rejected": ApprovalStatus.REJECTED,
        }
    )
)

_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


class ApprovalContractError(ValueError):
    """Raised when an approval envelope violates the domain contract."""


class ApprovalTransitionError(ApprovalContractError):
    """Raised when an approval lifecycle transition is not permitted."""

    def __init__(self, source: ApprovalStatus, target: ApprovalStatus) -> None:
        self.source = source
        self.target = target
        super().__init__(
            f"Approval cannot transition from {source.value} to {target.value}"
        )


@dataclass(frozen=True)
class NativeTargetIdentity:
    """Provider-native identity bound to the approved effect, when applicable."""

    provider_id: str
    resource_type: str
    resource_id: str
    parent_resource_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Revalidate this frozen value at a trust boundary."""

        _require_identifier("native_target.provider_id", self.provider_id)
        _require_identifier("native_target.resource_type", self.resource_type)
        _require_identifier("native_target.resource_id", self.resource_id)
        if self.parent_resource_id is not None:
            _require_identifier(
                "native_target.parent_resource_id", self.parent_resource_id
            )


@dataclass(frozen=True)
class ApprovalAuthority:
    """Authority that made an approval or rejection decision."""

    principal_type: PrincipalType
    principal_id: str
    authority_source: str
    authority_version: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Revalidate this frozen authority at a trust boundary."""

        _require_enum(
            "approving_authority.principal_type", self.principal_type, PrincipalType
        )
        _require_identifier("approving_authority.principal_id", self.principal_id)
        _require_identifier(
            "approving_authority.authority_source", self.authority_source
        )
        _require_identifier(
            "approving_authority.authority_version", self.authority_version
        )


@dataclass(frozen=True)
class ApprovalBinding:
    """Immutable identity, authority, evidence, and version scope of one effect."""

    approval_id: str
    schema_version: str
    tenant_id: str
    principal_type: PrincipalType
    principal_id: str
    workflow_id: str
    active_graph_revision: int
    task_id: str
    action_id: str
    capability_id: str
    tool_id: str
    effect_class: EffectClass
    native_target: NativeTargetIdentity | None
    input_hash: str
    payload_hash: str
    evidence_digest: str
    authority_hash: str
    registry_version: str
    registry_fingerprint: str
    harness_id: str
    harness_version: str
    policy_profile_id: str
    policy_version: str
    effect_idempotency_key: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Revalidate this frozen effect binding at a trust boundary."""

        _require_identifier("schema_version", self.schema_version)
        if self.schema_version != APPROVAL_ENVELOPE_SCHEMA_VERSION:
            raise ApprovalContractError(
                "approval schema_version must match the supported domain contract"
            )
        for field_name in (
            "approval_id",
            "tenant_id",
            "principal_id",
            "workflow_id",
            "task_id",
            "action_id",
            "capability_id",
            "tool_id",
            "registry_version",
            "harness_id",
            "harness_version",
            "policy_profile_id",
            "policy_version",
            "effect_idempotency_key",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_enum("principal_type", self.principal_type, PrincipalType)
        _require_enum("effect_class", self.effect_class, EffectClass)
        if type(self.active_graph_revision) is not int:
            raise ApprovalContractError(
                "active_graph_revision must be an exact integer"
            )
        if self.active_graph_revision < 1:
            raise ApprovalContractError("active_graph_revision must be positive")
        if (
            self.native_target is not None
            and type(self.native_target) is not NativeTargetIdentity
        ):
            raise ApprovalContractError(
                "native_target must be a NativeTargetIdentity or null"
            )
        if self.native_target is not None:
            self.native_target.validate()
        for field_name in (
            "input_hash",
            "payload_hash",
            "evidence_digest",
            "authority_hash",
            "registry_fingerprint",
        ):
            _require_digest(field_name, getattr(self, field_name))
        requested_at = _normalize_datetime("requested_at", self.requested_at)
        expires_at = _normalize_datetime("expires_at", self.expires_at)
        object.__setattr__(self, "requested_at", requested_at)
        object.__setattr__(self, "expires_at", expires_at)
        if expires_at <= requested_at:
            raise ApprovalContractError("expires_at must be after requested_at")


@dataclass(frozen=True)
class ApprovalEnvelope:
    """Immutable lifecycle snapshot whose digest is the authorization fingerprint."""

    binding: ApprovalBinding
    status: ApprovalStatus
    transitioned_at: datetime
    decided_at: datetime | None = None
    approving_authority: ApprovalAuthority | None = None
    revocation_reference: str | None = None
    supersession_reference: str | None = None
    fulfillment_receipt_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Revalidate the complete immutable snapshot at a trust boundary."""

        if type(self.binding) is not ApprovalBinding:
            raise ApprovalContractError("binding must be an ApprovalBinding")
        self.binding.validate()
        _require_enum("status", self.status, ApprovalStatus)
        transitioned_at = _normalize_datetime("transitioned_at", self.transitioned_at)
        object.__setattr__(self, "transitioned_at", transitioned_at)
        if transitioned_at < self.binding.requested_at:
            raise ApprovalContractError("transitioned_at cannot be before requested_at")
        if (self.decided_at is None) != (self.approving_authority is None):
            raise ApprovalContractError(
                "decided_at and approving_authority must be present together"
            )
        if self.approving_authority is not None:
            if type(self.approving_authority) is not ApprovalAuthority:
                raise ApprovalContractError(
                    "approving_authority must be an ApprovalAuthority"
                )
            self.approving_authority.validate()
        if self.decided_at is not None:
            decided_at = _normalize_datetime("decided_at", self.decided_at)
            object.__setattr__(self, "decided_at", decided_at)
            if not self.binding.requested_at <= decided_at < self.binding.expires_at:
                raise ApprovalContractError(
                    "decided_at must be within the approval request lifetime"
                )
            if transitioned_at < decided_at:
                raise ApprovalContractError(
                    "transitioned_at cannot be before decided_at"
                )
        _validate_lifecycle_metadata(self)


@dataclass(frozen=True)
class ApprovalTransition:
    source: ApprovalStatus
    target: ApprovalStatus

    def __post_init__(self) -> None:
        _require_enum("source", self.source, ApprovalStatus)
        _require_enum("target", self.target, ApprovalStatus)


def create_approval_request(binding: ApprovalBinding) -> ApprovalEnvelope:
    """Create the first immutable snapshot for a validated approval binding."""

    if type(binding) is not ApprovalBinding:
        raise ApprovalContractError("binding must be an ApprovalBinding")
    binding.validate()
    return ApprovalEnvelope(
        binding=binding,
        status=ApprovalStatus.REQUESTED,
        transitioned_at=binding.requested_at,
    )


def allowed_approval_transitions(status: ApprovalStatus) -> frozenset[ApprovalStatus]:
    _require_enum("status", status, ApprovalStatus)
    return _ALLOWED_APPROVAL_TRANSITIONS[status]


def can_transition_approval(source: ApprovalStatus, target: ApprovalStatus) -> bool:
    _require_enum("source", source, ApprovalStatus)
    _require_enum("target", target, ApprovalStatus)
    return target in allowed_approval_transitions(source)


def require_approval_transition(
    source: ApprovalStatus,
    target: ApprovalStatus,
) -> ApprovalTransition:
    if not can_transition_approval(source, target):
        raise ApprovalTransitionError(source, target)
    return ApprovalTransition(source=source, target=target)


def transition_approval(
    envelope: ApprovalEnvelope,
    target: ApprovalStatus,
    *,
    occurred_at: datetime,
    approving_authority: ApprovalAuthority | None = None,
    revocation_reference: str | None = None,
    supersession_reference: str | None = None,
    fulfillment_receipt_id: str | None = None,
) -> ApprovalEnvelope:
    """Return the next immutable snapshot after validating time and metadata."""

    if type(envelope) is not ApprovalEnvelope:
        raise ApprovalContractError("envelope must be an ApprovalEnvelope")
    envelope.validate()
    require_approval_transition(envelope.status, target)
    occurred_at = _normalize_datetime("occurred_at", occurred_at)
    if occurred_at < envelope.transitioned_at:
        raise ApprovalContractError(
            "approval transitions cannot move backwards in time"
        )
    _validate_transition_arguments(
        envelope=envelope,
        target=target,
        occurred_at=occurred_at,
        approving_authority=approving_authority,
        revocation_reference=revocation_reference,
        supersession_reference=supersession_reference,
        fulfillment_receipt_id=fulfillment_receipt_id,
    )
    decided_at = envelope.decided_at
    retained_authority = envelope.approving_authority
    if target in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        decided_at = occurred_at
        retained_authority = approving_authority
    return replace(
        envelope,
        status=target,
        transitioned_at=occurred_at,
        decided_at=decided_at,
        approving_authority=retained_authority,
        revocation_reference=revocation_reference,
        supersession_reference=supersession_reference,
        fulfillment_receipt_id=fulfillment_receipt_id,
    )


def approval_status_from_legacy_action_status(
    action_status: str | None,
) -> ApprovalStatus | None:
    """Map only explicit legacy decisions; execution state grants no authority."""

    normalized = str(action_status or "").strip().lower()
    return _LEGACY_ACTION_DECISION_STATUSES.get(normalized)


def _validate_lifecycle_metadata(envelope: ApprovalEnvelope) -> None:
    status = envelope.status
    has_decision = envelope.decided_at is not None
    if status in {ApprovalStatus.REVOKED, ApprovalStatus.SUPERSEDED} and (
        envelope.transitioned_at >= envelope.binding.expires_at
    ):
        raise ApprovalContractError(
            f"{status.value} approval cannot transition after approval expiry"
        )
    if status is ApprovalStatus.REQUESTED:
        if envelope.transitioned_at != envelope.binding.requested_at:
            raise ApprovalContractError(
                "requested approval must transition at requested_at"
            )
        if has_decision:
            raise ApprovalContractError("requested approval cannot contain a decision")
    elif status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        if not has_decision or envelope.transitioned_at != envelope.decided_at:
            raise ApprovalContractError(
                f"{status.value} approval requires its exact decision timestamp"
            )
    elif status is ApprovalStatus.EXPIRED:
        if envelope.transitioned_at < envelope.binding.expires_at:
            raise ApprovalContractError("approval cannot expire before expires_at")
    elif status is ApprovalStatus.REVOKED:
        if not has_decision:
            raise ApprovalContractError("only an approved grant can be revoked")
        _require_identifier("revocation_reference", envelope.revocation_reference)
    elif status is ApprovalStatus.SUPERSEDED:
        _require_identifier("supersession_reference", envelope.supersession_reference)
        if envelope.supersession_reference == envelope.binding.approval_id:
            raise ApprovalContractError("approval cannot supersede itself")
    elif status is ApprovalStatus.FULFILLED:
        if not has_decision:
            raise ApprovalContractError("only an approved grant can be fulfilled")
        _require_identifier("fulfillment_receipt_id", envelope.fulfillment_receipt_id)
    _reject_unexpected_lifecycle_metadata(envelope)


def _reject_unexpected_lifecycle_metadata(envelope: ApprovalEnvelope) -> None:
    if envelope.status is not ApprovalStatus.REVOKED and (
        envelope.revocation_reference is not None
    ):
        raise ApprovalContractError(
            "revocation_reference is valid only for revoked approval"
        )
    if envelope.status is not ApprovalStatus.SUPERSEDED and (
        envelope.supersession_reference is not None
    ):
        raise ApprovalContractError(
            "supersession_reference is valid only for superseded approval"
        )
    if envelope.status is not ApprovalStatus.FULFILLED and (
        envelope.fulfillment_receipt_id is not None
    ):
        raise ApprovalContractError(
            "fulfillment_receipt_id is valid only for fulfilled approval"
        )


def _validate_transition_arguments(
    *,
    envelope: ApprovalEnvelope,
    target: ApprovalStatus,
    occurred_at: datetime,
    approving_authority: ApprovalAuthority | None,
    revocation_reference: str | None,
    supersession_reference: str | None,
    fulfillment_receipt_id: str | None,
) -> None:
    if target in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        if approving_authority is None:
            raise ApprovalContractError(
                f"{target.value} transition requires approving_authority"
            )
    elif approving_authority is not None:
        raise ApprovalContractError(
            "approving_authority is accepted only for an approval decision"
        )
    expected_reference = {
        ApprovalStatus.REVOKED: revocation_reference,
        ApprovalStatus.SUPERSEDED: supersession_reference,
        ApprovalStatus.FULFILLED: fulfillment_receipt_id,
    }.get(target)
    if target in {
        ApprovalStatus.REVOKED,
        ApprovalStatus.SUPERSEDED,
        ApprovalStatus.FULFILLED,
    }:
        _require_identifier(f"{target.value}_reference", expected_reference)
    provided_references = {
        ApprovalStatus.REVOKED: revocation_reference,
        ApprovalStatus.SUPERSEDED: supersession_reference,
        ApprovalStatus.FULFILLED: fulfillment_receipt_id,
    }
    for reference_status, reference in provided_references.items():
        if reference is not None and target is not reference_status:
            raise ApprovalContractError(
                f"{reference_status.value} reference is invalid for {target.value}"
            )
    if target is ApprovalStatus.EXPIRED:
        if occurred_at < envelope.binding.expires_at:
            raise ApprovalContractError("approval cannot expire before expires_at")
    elif target is not ApprovalStatus.FULFILLED and (
        occurred_at >= envelope.binding.expires_at
    ):
        raise ApprovalContractError(
            f"{target.value} transition cannot occur after approval expiry"
        )


def _require_identifier(field_name: str, value: object) -> None:
    if type(value) is not str:
        raise ApprovalContractError(f"{field_name} must be an exact string")
    if not value or value != value.strip():
        raise ApprovalContractError(
            f"{field_name} must be a non-empty canonical string"
        )


def _require_digest(field_name: str, value: object) -> None:
    if type(value) is not str:
        raise ApprovalContractError(f"{field_name} must be an exact string")
    if _DIGEST_PATTERN.fullmatch(value) is None:
        raise ApprovalContractError(
            f"{field_name} must be a lowercase SHA-256 hex digest"
        )


def _require_enum(field_name: str, value: object, enum_type: type[Enum]) -> None:
    if type(value) is not enum_type:
        raise ApprovalContractError(f"{field_name} must be a supported enum value")


def _normalize_datetime(field_name: str, value: object) -> datetime:
    if type(value) is not datetime:
        raise ApprovalContractError(f"{field_name} must be an exact built-in datetime")
    if value.tzinfo is None:
        raise ApprovalContractError(f"{field_name} must be timezone-aware")
    if type(value.tzinfo) is not timezone:
        raise ApprovalContractError(
            f"{field_name} must use a built-in fixed-offset timezone"
        )
    return value.astimezone(timezone.utc)


__all__ = [
    "APPROVAL_ENVELOPE_CONTRACT",
    "APPROVAL_ENVELOPE_SCHEMA_VERSION",
    "TERMINAL_APPROVAL_STATUSES",
    "ApprovalAuthority",
    "ApprovalBinding",
    "ApprovalContractError",
    "ApprovalEnvelope",
    "ApprovalStatus",
    "ApprovalTransition",
    "ApprovalTransitionError",
    "EffectClass",
    "NativeTargetIdentity",
    "PrincipalType",
    "allowed_approval_transitions",
    "approval_status_from_legacy_action_status",
    "can_transition_approval",
    "create_approval_request",
    "require_approval_transition",
    "transition_approval",
]
