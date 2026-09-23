"""Platform-owned durable-history projection for the portability spike."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ast
import hashlib
import inspect
import json
import textwrap
from typing import Final

from domain.workflow.lifecycle import WorkflowStatus, can_transition_workflow
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityGraphRevision,
    PortabilityHistory,
    PortabilityInvariantError,
    PortabilityOperation,
    PortabilitySnapshot,
    PortabilityTaskOutcome,
    portability_command_digest,
    portability_task_is_schedulable,
    require_portability_revision_successor,
)


DURABLE_HISTORY_STATE_VERSION: Final = "workflow-durable-history.v1"
DURABLE_HISTORY_STRATEGY_ID: Final = "first-party-durable-history.v1"
_RECORD_TYPES: Final = frozenset(
    {
        "command_admitted",
        "effect_receipt_committed",
        "event_committed",
        "command_receipt_committed",
    }
)


@dataclass(frozen=True)
class DurableHistoryDefinition:
    strategy_id: str
    state_version: str
    record_contract_version: str


@dataclass(frozen=True)
class DurableHistoryRecord:
    sequence: int
    batch_sequence: int
    record_type: str
    command_id: str
    evidence_hash: str
    previous_record_hash: str
    record_hash: str


@dataclass(frozen=True)
class DurableHistoryHead:
    record_count: int
    record_head_hash: str


@dataclass(frozen=True)
class DurableHistoryProjection:
    state_version: str
    strategy_id: str
    definition_hash: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    workflow_status: str
    event_sequence: int
    history_hash: str
    record_count: int
    record_head_hash: str
    state_hash: str


DURABLE_HISTORY_DEFINITION: Final = DurableHistoryDefinition(
    strategy_id=DURABLE_HISTORY_STRATEGY_ID,
    state_version=DURABLE_HISTORY_STATE_VERSION,
    record_contract_version="durable-history-records.v1",
)


def verify_durable_history_definition(
    definition: DurableHistoryDefinition = DURABLE_HISTORY_DEFINITION,
) -> str:
    if type(definition) is not DurableHistoryDefinition:
        raise PortabilityInvariantError(
            "durable-history definition must use the exact contract"
        )
    if definition.state_version != DURABLE_HISTORY_STATE_VERSION:
        raise PortabilityInvariantError("unsupported durable-history state version")
    for value in (
        definition.strategy_id,
        definition.record_contract_version,
    ):
        if type(value) is not str or not value:
            raise PortabilityInvariantError(
                "durable-history definition identities must be non-empty"
            )
    return _sha256_json(
        {
            **asdict(definition),
            "implementation_digest": _implementation_digest(),
            "record_types": sorted(_RECORD_TYPES),
            "semantic_dependency_digests": _semantic_dependency_digests(),
        }
    )


def durable_history_evidence(
    history: PortabilityHistory,
) -> tuple[tuple[str, str, str], ...]:
    """Return the exact phase identities derivable from portable evidence."""

    effect_receipts = {item.command_id: item for item in history.effect_receipts}
    events = {item.command_id: item for item in history.events}
    command_receipts = {item.command_id: item for item in history.command_receipts}
    evidence: list[tuple[str, str, str]] = []
    for command in history.commands:
        evidence.append(
            (
                "command_admitted",
                command.command_id,
                portability_command_digest(command),
            )
        )
        effect_receipt = effect_receipts.get(command.command_id)
        if effect_receipt is not None:
            evidence.append(
                (
                    "effect_receipt_committed",
                    command.command_id,
                    _sha256_json(asdict(effect_receipt)),
                )
            )
        event = events.get(command.command_id)
        if event is not None:
            evidence.append(
                ("event_committed", command.command_id, _sha256_json(asdict(event)))
            )
        command_receipt = command_receipts.get(command.command_id)
        if command_receipt is not None:
            evidence.append(
                (
                    "command_receipt_committed",
                    command.command_id,
                    _sha256_json(asdict(command_receipt)),
                )
            )
    return tuple(evidence)


def durable_history_record_hash(
    *,
    sequence: int,
    batch_sequence: int,
    record_type: str,
    command_id: str,
    evidence_hash: str,
    previous_record_hash: str,
) -> str:
    return _sha256_json(
        {
            "batch_sequence": batch_sequence,
            "command_id": command_id,
            "evidence_hash": evidence_hash,
            "previous_record_hash": previous_record_hash,
            "record_type": record_type,
            "sequence": sequence,
        }
    )


def project_durable_history(
    history: PortabilityHistory,
    portable_snapshot: PortabilitySnapshot,
    records: tuple[DurableHistoryRecord, ...],
    head: DurableHistoryHead,
    *,
    definition: DurableHistoryDefinition = DURABLE_HISTORY_DEFINITION,
    expected_definition_hash: str,
) -> DurableHistoryProjection:
    if (
        portable_snapshot.tenant_id != history.tenant_id
        or portable_snapshot.workflow_id != history.workflow_id
        or portable_snapshot.graph_revision != history.graph_revision
        or portable_snapshot.last_event_sequence != len(history.events) - 1
    ):
        raise PortabilityInvariantError(
            "portable snapshot does not bind durable history"
        )
    definition_hash = verify_durable_history_definition(definition)
    if definition_hash != expected_definition_hash:
        raise PortabilityInvariantError("durable-history definition hash changed")
    if type(head) is not DurableHistoryHead:
        raise PortabilityInvariantError(
            "durable-history head must use the exact contract"
        )
    expected_evidence = set(durable_history_evidence(history))
    observed_evidence: set[tuple[str, str, str]] = set()
    previous_hash = "0" * 64
    for expected_sequence, record in enumerate(records):
        if type(record) is not DurableHistoryRecord:
            raise PortabilityInvariantError(
                "durable-history record must use the exact contract"
            )
        if (
            record.sequence != expected_sequence
            or record.record_type not in _RECORD_TYPES
        ):
            raise PortabilityInvariantError(
                "durable-history record sequence or type is invalid"
            )
        identity = (record.record_type, record.command_id, record.evidence_hash)
        if identity in observed_evidence:
            raise PortabilityInvariantError("durable-history evidence is duplicated")
        if (
            record.previous_record_hash != previous_hash
            or record.record_hash
            != durable_history_record_hash(
                sequence=record.sequence,
                batch_sequence=record.batch_sequence,
                record_type=record.record_type,
                command_id=record.command_id,
                evidence_hash=record.evidence_hash,
                previous_record_hash=record.previous_record_hash,
            )
        ):
            raise PortabilityInvariantError("durable-history hash chain is invalid")
        observed_evidence.add(identity)
        previous_hash = record.record_hash
    if head.record_count != len(records) or head.record_head_hash != previous_hash:
        raise PortabilityInvariantError(
            "durable-history chain does not match its persisted head"
        )
    if observed_evidence != expected_evidence:
        raise PortabilityInvariantError(
            "durable-history journal does not exactly cover portable evidence"
        )
    _verify_causal_order(history, records)
    state_payload = {
        "definition_hash": definition_hash,
        "graph_revision": history.graph_revision,
        "history_hash": history.history_hash,
        "record_head_hash": previous_hash,
        "record_count": len(records),
        "state_version": definition.state_version,
        "tenant_id": history.tenant_id,
        "workflow_id": history.workflow_id,
        "workflow_status": portable_snapshot.workflow_status,
    }
    return DurableHistoryProjection(
        state_version=definition.state_version,
        strategy_id=definition.strategy_id,
        definition_hash=definition_hash,
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
        graph_revision=history.graph_revision,
        workflow_status=portable_snapshot.workflow_status,
        event_sequence=len(history.events) - 1,
        history_hash=history.history_hash,
        record_count=len(records),
        record_head_hash=previous_hash,
        state_hash=_sha256_json(state_payload),
    )


def _verify_causal_order(
    history: PortabilityHistory,
    records: tuple[DurableHistoryRecord, ...],
) -> None:
    expected_by_command: dict[str, list[str]] = {}
    for record_type, command_id, _evidence_hash in durable_history_evidence(history):
        expected_by_command.setdefault(command_id, []).append(record_type)
    observed_by_command: dict[str, list[str]] = {}
    for record in records:
        observed_by_command.setdefault(record.command_id, []).append(record.record_type)
    if observed_by_command != expected_by_command:
        raise PortabilityInvariantError(
            "durable-history command phases violate causal order"
        )

    _verify_transaction_batches(expected_by_command, records)
    _verify_admissions_against_committed_state(history, records)

    event_commands = tuple(
        record.command_id
        for record in records
        if record.record_type == "event_committed"
    )
    receipt_commands = tuple(
        record.command_id
        for record in records
        if record.record_type == "command_receipt_committed"
    )
    authoritative_event_order = tuple(event.command_id for event in history.events)
    if (
        event_commands != authoritative_event_order
        or receipt_commands != authoritative_event_order
    ):
        raise PortabilityInvariantError(
            "durable-history commits violate authoritative event order"
        )


def _verify_transaction_batches(
    expected_by_command: dict[str, list[str]],
    records: tuple[DurableHistoryRecord, ...],
) -> None:
    batches: list[list[DurableHistoryRecord]] = []
    for record in records:
        if record.batch_sequence == len(batches):
            batches.append([record])
        elif record.batch_sequence == len(batches) - 1:
            batches[-1].append(record)
        else:
            raise PortabilityInvariantError(
                "durable-history transaction batches are not gap-free"
            )
    for batch in batches:
        command_ids = {record.command_id for record in batch}
        if len(command_ids) != 1:
            raise PortabilityInvariantError(
                "durable-history transaction batch crosses commands"
            )
        command_id = batch[0].command_id
        expected_phases = expected_by_command[command_id]
        actual_phases = [record.record_type for record in batch]
        first_phase = expected_phases.index(actual_phases[0])
        if (
            actual_phases
            != expected_phases[first_phase : first_phase + len(actual_phases)]
        ):
            raise PortabilityInvariantError(
                "durable-history transaction batch is not a causal phase segment"
            )
        if "event_committed" in actual_phases and actual_phases[-2:] != [
            "event_committed",
            "command_receipt_committed",
        ]:
            raise PortabilityInvariantError(
                "durable-history event and receipt commit batch was split"
            )


def _verify_admissions_against_committed_state(
    history: PortabilityHistory,
    records: tuple[DurableHistoryRecord, ...],
) -> None:
    """Replay only committed events before validating each admission boundary."""

    commands = {command.command_id: command for command in history.commands}
    status = WorkflowStatus.PLANNED
    attempts: dict[str, tuple[str, str, int, int]] = {}
    committed_effects: set[str] = set()
    topology_state = {"current": history.initial_topology}
    outcomes: dict[str, PortabilityTaskOutcome] = {}
    for record in records:
        command = commands[record.command_id]
        if record.record_type == "command_admitted":
            _require_admissible_from_committed_state(
                command,
                status=status,
                attempts=attempts,
                committed_effects=committed_effects,
                topology=topology_state["current"],
                outcomes=outcomes,
            )
        elif record.record_type == "event_committed":
            status = _apply_committed_command(
                command,
                status=status,
                attempts=attempts,
                committed_effects=committed_effects,
                topology_state=topology_state,
                outcomes=outcomes,
            )


def _require_admissible_from_committed_state(
    command: PortabilityCommand,
    *,
    status: WorkflowStatus,
    attempts: dict[str, tuple[str, str, int, int]],
    committed_effects: set[str],
    topology: PortabilityGraphRevision,
    outcomes: dict[str, PortabilityTaskOutcome],
) -> None:
    if command.graph_revision != topology.revision:
        _raise_invalid_admission(command)
    target_status = {
        PortabilityOperation.START_WORKFLOW: WorkflowStatus.RUNNING,
        PortabilityOperation.PAUSE_WORKFLOW: WorkflowStatus.PAUSED,
        PortabilityOperation.RESUME_WORKFLOW: WorkflowStatus.RUNNING,
        PortabilityOperation.COMPLETE_WORKFLOW: WorkflowStatus.COMPLETED,
        PortabilityOperation.CANCEL_WORKFLOW: WorkflowStatus.CANCELED,
    }.get(command.operation)
    if target_status is not None:
        if not can_transition_workflow(status, target_status):
            _raise_invalid_admission(command)
        return

    if status is not WorkflowStatus.RUNNING:
        _raise_invalid_admission(command)
    current = attempts.get(command.task_id or "")
    if command.operation is PortabilityOperation.ASSIGN_ATTEMPT:
        if (
            not portability_task_is_schedulable(
                topology, command.task_id or "", outcomes
            )
            or current is not None
            and int(command.fencing_token or 0) <= current[2]
        ):
            _raise_invalid_admission(command)
        return

    if command.operation is PortabilityOperation.COMMIT_GRAPH_REVISION:
        try:
            require_portability_revision_successor(
                topology,
                command.topology_revision or topology,
            )
        except ValueError:
            _raise_invalid_admission(command)
        return

    expected_identity = (
        command.attempt_id,
        command.worker_id,
        command.fencing_token,
    )
    if current is None or current[:3] != expected_identity:
        _raise_invalid_admission(command)
    if command.operation is PortabilityOperation.HEARTBEAT_ATTEMPT:
        if (
            command.task_id in outcomes
            or int(command.lease_expires_at_tick or 0) <= current[3]
        ):
            _raise_invalid_admission(command)
    elif command.operation is PortabilityOperation.RECORD_TASK_OUTCOME:
        if command.task_id in outcomes:
            _raise_invalid_admission(command)
    elif command.operation is PortabilityOperation.COMMIT_EFFECT:
        if command.task_id in outcomes or command.effect_id in committed_effects:
            _raise_invalid_admission(command)


def _apply_committed_command(
    command: PortabilityCommand,
    *,
    status: WorkflowStatus,
    attempts: dict[str, tuple[str, str, int, int]],
    committed_effects: set[str],
    topology_state: dict[str, PortabilityGraphRevision],
    outcomes: dict[str, PortabilityTaskOutcome],
) -> WorkflowStatus:
    target_status = {
        PortabilityOperation.START_WORKFLOW: WorkflowStatus.RUNNING,
        PortabilityOperation.PAUSE_WORKFLOW: WorkflowStatus.PAUSED,
        PortabilityOperation.RESUME_WORKFLOW: WorkflowStatus.RUNNING,
        PortabilityOperation.COMPLETE_WORKFLOW: WorkflowStatus.COMPLETED,
        PortabilityOperation.CANCEL_WORKFLOW: WorkflowStatus.CANCELED,
    }.get(command.operation)
    if target_status is not None:
        return target_status
    if command.operation in {
        PortabilityOperation.ASSIGN_ATTEMPT,
        PortabilityOperation.HEARTBEAT_ATTEMPT,
    }:
        attempts[command.task_id or ""] = (
            command.attempt_id or "",
            command.worker_id or "",
            int(command.fencing_token or 0),
            int(command.lease_expires_at_tick or 0),
        )
    elif command.operation is PortabilityOperation.COMMIT_EFFECT:
        committed_effects.add(command.effect_id or "")
    elif command.operation is PortabilityOperation.COMMIT_GRAPH_REVISION:
        if command.topology_revision is None:
            _raise_invalid_admission(command)
        topology_state["current"] = command.topology_revision
    elif command.operation is PortabilityOperation.RECORD_TASK_OUTCOME:
        if command.task_outcome is None:
            _raise_invalid_admission(command)
        outcomes[command.task_id or ""] = command.task_outcome
    return status


def _raise_invalid_admission(command: PortabilityCommand) -> None:
    raise PortabilityInvariantError(
        "durable-history command admission violates committed lifecycle "
        f"prerequisites: {command.command_id}"
    )


def _implementation_digest() -> str:
    return _module_implementation_digest(
        _implementation_digest,
        dependency_name="durable-history",
    )


def _semantic_dependency_digests() -> dict[str, str]:
    lifecycle_matrix = [
        (source.value, target.value)
        for source in WorkflowStatus
        for target in WorkflowStatus
        if can_transition_workflow(source, target)
    ]
    lifecycle_digest = _sha256_json(
        {
            "implementation_digest": _module_implementation_digest(
                WorkflowStatus,
                dependency_name="workflow lifecycle",
            ),
            "statuses": [status.value for status in WorkflowStatus],
            "transitions": lifecycle_matrix,
        }
    )
    operation_schema_digest = _sha256_json(
        {
            "command_signature": str(
                inspect.signature(PortabilityCommand, follow_wrapped=False)
            ),
            "implementation_digest": _module_implementation_digest(
                PortabilityCommand,
                dependency_name="portability operation schema",
            ),
            "operations": [operation.value for operation in PortabilityOperation],
        }
    )
    return {
        "portability_operation_schema": operation_schema_digest,
        "workflow_lifecycle": lifecycle_digest,
    }


def _module_implementation_digest(
    symbol: object,
    *,
    dependency_name: str,
) -> str:
    module = inspect.getmodule(symbol)
    if module is None:
        raise PortabilityInvariantError(
            f"{dependency_name} implementation module is unavailable"
        )
    try:
        syntax = ast.parse(textwrap.dedent(inspect.getsource(module)))
    except (OSError, TypeError, SyntaxError) as exc:
        raise PortabilityInvariantError(
            f"{dependency_name} implementation source is unavailable"
        ) from exc
    return hashlib.sha256(
        ast.dump(syntax, annotate_fields=True, include_attributes=False).encode("utf-8")
    ).hexdigest()


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "DURABLE_HISTORY_DEFINITION",
    "DURABLE_HISTORY_STATE_VERSION",
    "DURABLE_HISTORY_STRATEGY_ID",
    "DurableHistoryDefinition",
    "DurableHistoryHead",
    "DurableHistoryProjection",
    "DurableHistoryRecord",
    "durable_history_evidence",
    "durable_history_record_hash",
    "project_durable_history",
    "verify_durable_history_definition",
]
