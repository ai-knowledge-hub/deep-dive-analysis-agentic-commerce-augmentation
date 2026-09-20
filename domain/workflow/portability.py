"""Framework-neutral contracts for the workflow portability spike.

Model output may propose commands in later slices, but it cannot define
workflow identity, authority, leases, idempotency, or committed effects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Final


PORTABILITY_CONTRACT_VERSION: Final = "workflow-portability.v2"


class PortabilityOperation(str, Enum):
    START_WORKFLOW = "start_workflow"
    PAUSE_WORKFLOW = "pause_workflow"
    RESUME_WORKFLOW = "resume_workflow"
    ASSIGN_ATTEMPT = "assign_attempt"
    HEARTBEAT_ATTEMPT = "heartbeat_attempt"
    COMMIT_EFFECT = "commit_effect"
    COMPLETE_WORKFLOW = "complete_workflow"
    CANCEL_WORKFLOW = "cancel_workflow"


class PortabilityFaultPoint(str, Enum):
    BEFORE_EFFECT = "before_effect"
    AFTER_EFFECT_BEFORE_RECEIPT = "after_effect_before_receipt"
    AFTER_RECEIPT_BEFORE_EVENT_COMMIT = "after_receipt_before_event_commit"
    BEFORE_EVENT_COMMIT = "before_event_commit"
    AFTER_EVENT_COMMIT_BEFORE_ACK = "after_event_commit_before_ack"


class PortabilityInvariantError(RuntimeError):
    """Raised when an adapter would violate benchmark invariants."""


class PortabilityConflictError(PortabilityInvariantError):
    """Raised when an immutable identity is reused differently."""


class PortabilityInjectedCrash(RuntimeError):
    def __init__(self, point: PortabilityFaultPoint, *, effect_executed: bool) -> None:
        self.point = point
        self.effect_executed = effect_executed
        super().__init__(f"injected crash at {point.value}")


class PortabilityContractError(ValueError):
    """Raised when benchmark input violates the shared adapter contract."""


@dataclass(frozen=True)
class PortabilityCommand:
    command_id: str
    tenant_id: str
    workflow_id: str
    operation: PortabilityOperation
    graph_revision: int = 1
    task_id: str | None = None
    attempt_id: str | None = None
    worker_id: str | None = None
    fencing_token: int | None = None
    lease_expires_at_tick: int | None = None
    effect_id: str | None = None
    payload_hash: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("command_id", "tenant_id", "workflow_id"):
            _require_nonempty_string(getattr(self, field_name), field_name)
        if type(self.operation) is not PortabilityOperation:
            raise PortabilityContractError("operation must be a PortabilityOperation")
        if type(self.graph_revision) is not int or self.graph_revision < 1:
            raise PortabilityContractError("graph_revision must be a positive integer")

        attempt_operations = {
            PortabilityOperation.ASSIGN_ATTEMPT,
            PortabilityOperation.HEARTBEAT_ATTEMPT,
            PortabilityOperation.COMMIT_EFFECT,
        }
        if self.operation in attempt_operations:
            _require_nonempty_string(self.task_id, "task_id")
            _require_nonempty_string(self.attempt_id, "attempt_id")
            _require_nonempty_string(self.worker_id, "worker_id")
            if type(self.fencing_token) is not int or self.fencing_token < 1:
                raise PortabilityContractError(
                    "fencing_token must be a positive integer"
                )
        elif any(
            value is not None
            for value in (
                self.task_id,
                self.attempt_id,
                self.worker_id,
                self.fencing_token,
                self.lease_expires_at_tick,
            )
        ):
            raise PortabilityContractError(
                f"{self.operation.value} cannot carry attempt or lease identity"
            )

        if self.operation in {
            PortabilityOperation.ASSIGN_ATTEMPT,
            PortabilityOperation.HEARTBEAT_ATTEMPT,
        }:
            if (
                type(self.lease_expires_at_tick) is not int
                or self.lease_expires_at_tick < 1
            ):
                raise PortabilityContractError(
                    f"{self.operation.value} requires a positive lease expiry"
                )
        elif self.lease_expires_at_tick is not None:
            raise PortabilityContractError(
                f"{self.operation.value} cannot carry a lease expiry"
            )

        if self.operation is PortabilityOperation.COMMIT_EFFECT:
            _require_nonempty_string(self.effect_id, "effect_id")
            if not _is_sha256(self.payload_hash):
                raise PortabilityContractError(
                    "commit_effect requires a lowercase SHA-256 payload_hash"
                )
        elif self.effect_id is not None or self.payload_hash is not None:
            raise PortabilityContractError(
                f"{self.operation.value} cannot carry effect identity"
            )


@dataclass(frozen=True)
class PortabilityEvent:
    sequence: int
    tenant_id: str
    workflow_id: str
    event_type: str
    command_id: str
    payload_json: str


@dataclass(frozen=True)
class PortabilityCommandReceipt:
    command_id: str
    request_hash: str
    first_event_sequence: int
    last_event_sequence: int


@dataclass(frozen=True)
class PortabilityEffectExecution:
    command: PortabilityCommand
    request_hash: str
    provider_receipt_id: str


@dataclass(frozen=True)
class PortabilityEffectReceipt:
    effect_id: str
    command_id: str
    request_hash: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    task_id: str
    attempt_id: str
    worker_id: str
    fencing_token: int
    payload_hash: str
    provider_receipt_id: str


@dataclass(frozen=True)
class PortabilityHistory:
    contract_version: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    commands: tuple[PortabilityCommand, ...]
    events: tuple[PortabilityEvent, ...]
    command_receipts: tuple[PortabilityCommandReceipt, ...]
    effect_receipts: tuple[PortabilityEffectReceipt, ...]
    history_hash: str


@dataclass(frozen=True)
class PortabilitySnapshot:
    tenant_id: str
    workflow_id: str
    workflow_status: str
    graph_revision: int
    active_attempts: tuple[tuple[str, str, str, int, int], ...]
    committed_effects: tuple[tuple[str, str, str], ...]
    last_event_sequence: int


@dataclass(frozen=True)
class PortabilityCheckpoint:
    contract_version: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    event_sequence: int
    history_hash: str
    committed_receipt_ids: tuple[str, ...]
    snapshot: PortabilitySnapshot


def canonical_command_payload(command: PortabilityCommand) -> dict[str, object]:
    return {
        **asdict(command),
        "contract_version": PORTABILITY_CONTRACT_VERSION,
        "operation": command.operation.value,
    }


def portability_command_digest(command: PortabilityCommand) -> str:
    return _sha256_json(canonical_command_payload(command))


def portability_history_digest(
    *,
    tenant_id: str,
    workflow_id: str,
    graph_revision: int,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
    command_receipts: tuple[PortabilityCommandReceipt, ...],
    effect_receipts: tuple[PortabilityEffectReceipt, ...],
) -> str:
    return _sha256_json(
        {
            "command_receipts": [asdict(receipt) for receipt in command_receipts],
            "commands": [canonical_command_payload(command) for command in commands],
            "contract_version": PORTABILITY_CONTRACT_VERSION,
            "effect_receipts": [asdict(receipt) for receipt in effect_receipts],
            "events": [asdict(event) for event in events],
            "graph_revision": graph_revision,
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
        }
    )


def canonical_event_payload(payload: dict[str, object]) -> str:
    return _canonical_json(payload)


def _require_nonempty_string(value: object, field_name: str) -> None:
    if type(value) is not str or not value:
        raise PortabilityContractError(f"{field_name} must be a non-empty string")


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and not any(character not in "0123456789abcdef" for character in value)
    )


def _sha256_json(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = [
    "PORTABILITY_CONTRACT_VERSION",
    "PortabilityCheckpoint",
    "PortabilityCommand",
    "PortabilityCommandReceipt",
    "PortabilityConflictError",
    "PortabilityContractError",
    "PortabilityEffectExecution",
    "PortabilityEffectReceipt",
    "PortabilityEvent",
    "PortabilityFaultPoint",
    "PortabilityHistory",
    "PortabilityInjectedCrash",
    "PortabilityInvariantError",
    "PortabilityOperation",
    "PortabilitySnapshot",
    "canonical_command_payload",
    "canonical_event_payload",
    "portability_command_digest",
    "portability_history_digest",
]
