"""Independent replay of authoritative portable workflow evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Callable

from domain.workflow.lifecycle import WorkflowStatus, require_workflow_transition
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityEdgeDefinition,
    PortabilityEffectReceipt,
    PortabilityEvent,
    PortabilityGraphRevision,
    PortabilityInvariantError,
    PortabilityJoinDefinition,
    PortabilityJoinPolicy,
    PortabilityOperation,
    PortabilitySnapshot,
    PortabilityTaskDefinition,
    PortabilityTaskOutcome,
    canonical_event_payload,
    canonical_graph_revision_payload,
    portability_graph_revision_digest,
    portability_join_states,
    portability_task_is_schedulable,
    require_portability_revision_successor,
)


AttemptState = tuple[str, str, int, int]
OutcomeState = tuple[PortabilityTaskOutcome, str | None]


@dataclass
class _ReplayState:
    tenant_id: str
    workflow_id: str
    topology: PortabilityGraphRevision
    status: WorkflowStatus = WorkflowStatus.PLANNED
    attempts: dict[str, AttemptState] = field(default_factory=dict)
    attempt_identities: set[tuple[str, str, str, int]] = field(default_factory=set)
    effects: dict[str, tuple[str, str]] = field(default_factory=dict)
    outcomes: dict[str, OutcomeState] = field(default_factory=dict)


def replay_portability_history(
    *,
    tenant_id: str,
    workflow_id: str,
    initial_topology: PortabilityGraphRevision,
    expected_graph_revision: int,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
    effect_receipts: tuple[PortabilityEffectReceipt, ...],
) -> PortabilitySnapshot:
    state = _ReplayState(tenant_id, workflow_id, initial_topology)
    command_map = {command.command_id: command for command in commands}
    receipt_map = {receipt.effect_id: receipt for receipt in effect_receipts}
    for expected_sequence, event in enumerate(events):
        command, payload = _validated_event(
            state,
            event,
            expected_sequence=expected_sequence,
            commands=command_map,
        )
        _EVENT_HANDLERS[event.event_type](state, command, payload, receipt_map)
    if state.topology.revision != expected_graph_revision:
        raise PortabilityInvariantError(
            "history graph revision does not match topology replay"
        )
    return _snapshot(
        state,
        initial_topology=initial_topology,
        commands=commands,
        events=events,
    )


def active_graph_revision(
    initial_topology: PortabilityGraphRevision,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
) -> int:
    command_map = {command.command_id: command for command in commands}
    revision = initial_topology.revision
    for event in events:
        command = command_map.get(event.command_id)
        if (
            event.event_type == "graph_revision_committed"
            and command is not None
            and command.topology_revision is not None
        ):
            revision = command.topology_revision.revision
    return revision


def snapshot_graph_revision(snapshot: PortabilitySnapshot) -> PortabilityGraphRevision:
    return PortabilityGraphRevision(
        revision=snapshot.graph_revision,
        parent_revision=(
            snapshot.graph_revision - 1
            if snapshot.graph_revision > snapshot.initial_graph_revision
            else None
        ),
        tasks=tuple(
            PortabilityTaskDefinition(task_id, task_type)
            for task_id, task_type, _introduced_revision in snapshot.graph_tasks
        ),
        edges=tuple(
            PortabilityEdgeDefinition(from_task, to_task, join_group)
            for from_task, to_task, join_group, _introduced_revision in snapshot.graph_edges
        ),
        joins=tuple(
            PortabilityJoinDefinition(
                join_group,
                target_task,
                PortabilityJoinPolicy(policy),
                quorum,
            )
            for join_group, target_task, policy, quorum, _introduced in snapshot.graph_joins
        ),
    )


def snapshot_task_is_schedulable(snapshot: PortabilitySnapshot, task_id: str) -> bool:
    return portability_task_is_schedulable(
        snapshot_graph_revision(snapshot),
        task_id,
        {
            outcome_task_id: PortabilityTaskOutcome(outcome)
            for outcome_task_id, outcome, _result_hash in snapshot.task_outcomes
        },
    )


def _validated_event(
    state: _ReplayState,
    event: PortabilityEvent,
    *,
    expected_sequence: int,
    commands: dict[str, PortabilityCommand],
) -> tuple[PortabilityCommand, dict[str, object]]:
    if type(event.sequence) is not int or event.sequence != expected_sequence:
        raise PortabilityInvariantError("event history must be gap-free")
    if event.tenant_id != state.tenant_id or event.workflow_id != state.workflow_id:
        raise PortabilityInvariantError("event scope does not match history")
    command = commands.get(event.command_id)
    if command is None:
        raise PortabilityInvariantError("event lacks command evidence")
    revision_matches = command.graph_revision == state.topology.revision
    stale_effect_reconciliation = (
        event.event_type == "effect_reconciled"
        and command.operation is PortabilityOperation.COMMIT_EFFECT
        and command.graph_revision < state.topology.revision
    )
    if not revision_matches and not stale_effect_reconciliation:
        raise PortabilityInvariantError(
            "event command does not match the active graph revision"
        )
    if event.event_type not in _expected_event_types(command.operation):
        raise PortabilityInvariantError("event type does not match command")
    return command, _event_payload(event)


def _apply_lifecycle(
    state: _ReplayState,
    _command: PortabilityCommand,
    payload: dict[str, object],
    _receipts: dict[str, PortabilityEffectReceipt],
    *,
    target: WorkflowStatus,
) -> None:
    _require_payload_keys(payload, frozenset())
    _transition(state.status, target)
    state.status = target


def _apply_attempt_assignment(
    state: _ReplayState,
    command: PortabilityCommand,
    payload: dict[str, object],
    _receipts: dict[str, PortabilityEffectReceipt],
) -> None:
    _require_running(state.status, "attempt assigned")
    attempt = _attempt_payload(payload)
    _require_attempt_payload_matches_command(payload, command)
    if not portability_task_is_schedulable(
        state.topology,
        command.task_id or "",
        {task_id: outcome for task_id, (outcome, _result) in state.outcomes.items()},
    ):
        raise PortabilityInvariantError("attempt assigned to unschedulable task")
    current = state.attempts.get(command.task_id or "")
    if current is not None and attempt[2] <= current[2]:
        raise PortabilityInvariantError("attempt fencing history is not monotonic")
    state.attempts[command.task_id or ""] = attempt
    state.attempt_identities.add(
        (
            command.task_id or "",
            command.attempt_id or "",
            command.worker_id or "",
            int(command.fencing_token or 0),
        )
    )


def _apply_attempt_heartbeat(
    state: _ReplayState,
    command: PortabilityCommand,
    payload: dict[str, object],
    _receipts: dict[str, PortabilityEffectReceipt],
) -> None:
    _require_running(state.status, "attempt heartbeat")
    if command.task_id in state.outcomes:
        raise PortabilityInvariantError("completed task heartbeat is not permitted")
    attempt = _attempt_payload(payload)
    _require_attempt_payload_matches_command(payload, command)
    current = state.attempts.get(command.task_id or "")
    if current is None or attempt[:3] != current[:3] or attempt[3] <= current[3]:
        raise PortabilityInvariantError("heartbeat does not extend current lease")
    state.attempts[command.task_id or ""] = attempt


def _apply_effect(
    state: _ReplayState,
    command: PortabilityCommand,
    payload: dict[str, object],
    receipts: dict[str, PortabilityEffectReceipt],
) -> None:
    identity = (
        command.task_id or "",
        command.attempt_id or "",
        command.worker_id or "",
        int(command.fencing_token or 0),
    )
    if identity not in state.attempt_identities:
        raise PortabilityInvariantError("effect lacks prior attempt assignment")
    effect_id, payload_hash, provider_receipt_id = _effect_payload(payload)
    _require_effect_payload_matches_command(payload, command)
    receipt = receipts.get(effect_id)
    if receipt is None or (
        receipt.command_id != command.command_id
        or receipt.payload_hash != payload_hash
        or receipt.provider_receipt_id != provider_receipt_id
    ):
        raise PortabilityInvariantError("effect event lacks matching receipt")
    if effect_id in state.effects:
        raise PortabilityInvariantError("effect identity committed more than once")
    state.effects[effect_id] = (payload_hash, provider_receipt_id)


def _apply_committed_effect(
    state: _ReplayState,
    command: PortabilityCommand,
    payload: dict[str, object],
    receipts: dict[str, PortabilityEffectReceipt],
) -> None:
    _require_running(state.status, "effect committed")
    if command.task_id in state.outcomes:
        raise PortabilityInvariantError("completed task effect is not permitted")
    current = state.attempts.get(command.task_id or "")
    expected = (command.attempt_id, command.worker_id, command.fencing_token)
    if current is None or current[:3] != expected:
        raise PortabilityInvariantError("effect committed by stale attempt")
    _apply_effect(state, command, payload, receipts)


def _apply_graph_revision(
    state: _ReplayState,
    command: PortabilityCommand,
    payload: dict[str, object],
    _receipts: dict[str, PortabilityEffectReceipt],
) -> None:
    _require_running(state.status, "graph revision committed")
    candidate = command.topology_revision
    if candidate is None:
        raise PortabilityInvariantError(
            "graph revision event lacks command topology evidence"
        )
    _require_graph_revision_payload_matches_command(payload, command)
    try:
        require_portability_revision_successor(state.topology, candidate)
    except ValueError as exc:
        raise PortabilityInvariantError(str(exc)) from exc
    state.topology = candidate


def _apply_task_outcome(
    state: _ReplayState,
    command: PortabilityCommand,
    payload: dict[str, object],
    _receipts: dict[str, PortabilityEffectReceipt],
) -> None:
    _require_running(state.status, "task outcome recorded")
    _require_task_outcome_payload_matches_command(payload, command)
    task_id = command.task_id or ""
    if task_id not in {task.task_id for task in state.topology.tasks}:
        raise PortabilityInvariantError("task outcome references unknown active task")
    current = state.attempts.get(task_id)
    expected = (command.attempt_id, command.worker_id, command.fencing_token)
    if current is None or current[:3] != expected:
        raise PortabilityInvariantError("task outcome was committed by a stale attempt")
    if task_id in state.outcomes:
        raise PortabilityInvariantError(
            "task outcome identity committed more than once"
        )
    state.outcomes[task_id] = (
        command.task_outcome or PortabilityTaskOutcome.FAILED,
        command.result_hash,
    )


EventHandler = Callable[
    [
        _ReplayState,
        PortabilityCommand,
        dict[str, object],
        dict[str, PortabilityEffectReceipt],
    ],
    None,
]


def _lifecycle_handler(target: WorkflowStatus) -> EventHandler:
    def apply(
        state: _ReplayState,
        command: PortabilityCommand,
        payload: dict[str, object],
        receipts: dict[str, PortabilityEffectReceipt],
    ) -> None:
        _apply_lifecycle(state, command, payload, receipts, target=target)

    return apply


_EVENT_HANDLERS: dict[str, EventHandler] = {
    "workflow_started": _lifecycle_handler(WorkflowStatus.RUNNING),
    "workflow_paused": _lifecycle_handler(WorkflowStatus.PAUSED),
    "workflow_resumed": _lifecycle_handler(WorkflowStatus.RUNNING),
    "attempt_assigned": _apply_attempt_assignment,
    "attempt_heartbeat": _apply_attempt_heartbeat,
    "effect_committed": _apply_committed_effect,
    "effect_reconciled": _apply_effect,
    "graph_revision_committed": _apply_graph_revision,
    "task_outcome_recorded": _apply_task_outcome,
    "workflow_completed": _lifecycle_handler(WorkflowStatus.COMPLETED),
    "workflow_canceled": _lifecycle_handler(WorkflowStatus.CANCELED),
}


def _snapshot(
    state: _ReplayState,
    *,
    initial_topology: PortabilityGraphRevision,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
) -> PortabilitySnapshot:
    revisions = _committed_topologies(initial_topology, commands, events)
    introduced_tasks = _introduced_task_revisions(revisions)
    outcomes = {
        task_id: outcome for task_id, (outcome, _result) in state.outcomes.items()
    }
    join_states = portability_join_states(state.topology, outcomes)
    return PortabilitySnapshot(
        tenant_id=state.tenant_id,
        workflow_id=state.workflow_id,
        workflow_status=state.status.value,
        initial_graph_revision=initial_topology.revision,
        graph_revision=state.topology.revision,
        graph_tasks=tuple(
            (task.task_id, task.task_type, introduced_tasks[task.task_id])
            for task in state.topology.tasks
        ),
        graph_edges=tuple(
            (*_edge_identity(edge), _introduced_revision(revisions, edge, "edges"))
            for edge in state.topology.edges
        ),
        graph_joins=tuple(
            (
                join.join_group_id,
                join.target_task_id,
                join.policy.value,
                join.quorum,
                _introduced_revision(revisions, join, "joins"),
            )
            for join in state.topology.joins
        ),
        task_outcomes=tuple(
            (task_id, outcome.value, result_hash)
            for task_id, (outcome, result_hash) in sorted(state.outcomes.items())
        ),
        join_states=tuple(
            (join_id, join_state.value) for join_id, join_state in join_states
        ),
        active_attempts=tuple(
            (task_id, attempt_id, worker_id, token, expiry)
            for task_id, (attempt_id, worker_id, token, expiry) in sorted(
                state.attempts.items()
            )
            if task_id not in state.outcomes
        ),
        committed_effects=tuple(
            (effect_id, payload_hash, provider_receipt_id)
            for effect_id, (payload_hash, provider_receipt_id) in sorted(
                state.effects.items()
            )
        ),
        last_event_sequence=len(events) - 1,
    )


def _committed_topologies(
    initial: PortabilityGraphRevision,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
) -> tuple[PortabilityGraphRevision, ...]:
    command_map = {command.command_id: command for command in commands}
    revisions = [initial]
    for event in events:
        command = command_map.get(event.command_id)
        if event.event_type == "graph_revision_committed" and command is not None:
            if command.topology_revision is None:
                raise PortabilityInvariantError(
                    "graph revision event lacks topology evidence"
                )
            revisions.append(command.topology_revision)
    return tuple(revisions)


def _introduced_task_revisions(
    revisions: tuple[PortabilityGraphRevision, ...],
) -> dict[str, int]:
    introduced: dict[str, int] = {}
    for revision in revisions:
        for task in revision.tasks:
            introduced.setdefault(task.task_id, revision.revision)
    return introduced


def _introduced_revision(
    revisions: tuple[PortabilityGraphRevision, ...],
    evidence: PortabilityEdgeDefinition | PortabilityJoinDefinition,
    collection: str,
) -> int:
    return next(
        revision.revision
        for revision in revisions
        if evidence in getattr(revision, collection)
    )


def _edge_identity(edge: PortabilityEdgeDefinition) -> tuple[str, str, str]:
    return edge.from_task_id, edge.to_task_id, edge.join_group_id


def _event_payload(event: PortabilityEvent) -> dict[str, object]:
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PortabilityInvariantError("event payload is not valid JSON") from exc
    if type(payload) is not dict:
        raise PortabilityInvariantError("event payload must be an object")
    if canonical_event_payload(payload) != event.payload_json:
        raise PortabilityInvariantError("event payload must be canonical")
    return payload


def _attempt_payload(payload: dict[str, object]) -> AttemptState:
    _require_payload_keys(
        payload,
        frozenset(
            {
                "task_id",
                "attempt_id",
                "worker_id",
                "fencing_token",
                "lease_expires_at_tick",
            }
        ),
    )
    return (
        _payload_string(payload, "attempt_id"),
        _payload_string(payload, "worker_id"),
        _payload_integer(payload, "fencing_token"),
        _payload_integer(payload, "lease_expires_at_tick"),
    )


def _effect_payload(payload: dict[str, object]) -> tuple[str, str, str]:
    _require_payload_keys(
        payload,
        frozenset(
            {
                "task_id",
                "attempt_id",
                "worker_id",
                "fencing_token",
                "effect_id",
                "payload_hash",
                "provider_receipt_id",
            }
        ),
    )
    return (
        _payload_string(payload, "effect_id"),
        _payload_string(payload, "payload_hash"),
        _payload_string(payload, "provider_receipt_id"),
    )


def _require_attempt_payload_matches_command(
    payload: dict[str, object], command: PortabilityCommand
) -> None:
    if (
        payload["task_id"] != command.task_id
        or payload["attempt_id"] != command.attempt_id
        or payload["worker_id"] != command.worker_id
        or payload["fencing_token"] != command.fencing_token
        or payload["lease_expires_at_tick"] != command.lease_expires_at_tick
    ):
        raise PortabilityInvariantError("attempt event does not match command")


def _require_effect_payload_matches_command(
    payload: dict[str, object], command: PortabilityCommand
) -> None:
    if (
        payload["task_id"] != command.task_id
        or payload["attempt_id"] != command.attempt_id
        or payload["worker_id"] != command.worker_id
        or payload["fencing_token"] != command.fencing_token
        or payload["effect_id"] != command.effect_id
        or payload["payload_hash"] != command.payload_hash
    ):
        raise PortabilityInvariantError("effect event does not match command")


def _require_graph_revision_payload_matches_command(
    payload: dict[str, object], command: PortabilityCommand
) -> None:
    revision = command.topology_revision
    if revision is None:
        raise PortabilityInvariantError(
            "graph revision event lacks command topology evidence"
        )
    expected = {
        **canonical_graph_revision_payload(revision),
        "graph_hash": portability_graph_revision_digest(revision),
    }
    if payload != expected:
        raise PortabilityInvariantError(
            "graph revision event does not match command evidence"
        )


def _require_task_outcome_payload_matches_command(
    payload: dict[str, object], command: PortabilityCommand
) -> None:
    _require_payload_keys(
        payload,
        frozenset(
            {
                "attempt_id",
                "fencing_token",
                "result_hash",
                "task_id",
                "task_outcome",
                "worker_id",
            }
        ),
    )
    if (
        payload["task_id"] != command.task_id
        or payload["attempt_id"] != command.attempt_id
        or payload["worker_id"] != command.worker_id
        or payload["fencing_token"] != command.fencing_token
        or payload["task_outcome"]
        != (command.task_outcome.value if command.task_outcome else None)
        or payload["result_hash"] != command.result_hash
    ):
        raise PortabilityInvariantError("task outcome event does not match command")


def _expected_event_types(operation: PortabilityOperation) -> frozenset[str]:
    if operation is PortabilityOperation.COMMIT_EFFECT:
        return frozenset({"effect_committed", "effect_reconciled"})
    return frozenset(
        {
            {
                PortabilityOperation.START_WORKFLOW: "workflow_started",
                PortabilityOperation.PAUSE_WORKFLOW: "workflow_paused",
                PortabilityOperation.RESUME_WORKFLOW: "workflow_resumed",
                PortabilityOperation.ASSIGN_ATTEMPT: "attempt_assigned",
                PortabilityOperation.HEARTBEAT_ATTEMPT: "attempt_heartbeat",
                PortabilityOperation.COMMIT_GRAPH_REVISION: "graph_revision_committed",
                PortabilityOperation.RECORD_TASK_OUTCOME: "task_outcome_recorded",
                PortabilityOperation.COMPLETE_WORKFLOW: "workflow_completed",
                PortabilityOperation.CANCEL_WORKFLOW: "workflow_canceled",
            }[operation]
        }
    )


def _require_running(status: WorkflowStatus, operation: str) -> None:
    if status is not WorkflowStatus.RUNNING:
        raise PortabilityInvariantError(f"{operation} outside running workflow")


def _transition(source: WorkflowStatus, target: WorkflowStatus) -> None:
    try:
        require_workflow_transition(source, target)
    except ValueError as exc:
        raise PortabilityInvariantError(str(exc)) from exc


def _payload_string(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if type(value) is not str or not value:
        raise PortabilityInvariantError(f"event {field_name} must be a string")
    return value


def _payload_integer(payload: dict[str, object], field_name: str) -> int:
    value = payload.get(field_name)
    if type(value) is not int or value < 1:
        raise PortabilityInvariantError(f"event {field_name} must be positive")
    return value


def _require_payload_keys(payload: dict[str, object], expected: frozenset[str]) -> None:
    if frozenset(payload) != expected:
        raise PortabilityInvariantError("event payload fields do not match contract")


__all__ = [
    "active_graph_revision",
    "replay_portability_history",
    "snapshot_graph_revision",
    "snapshot_task_is_schedulable",
]
