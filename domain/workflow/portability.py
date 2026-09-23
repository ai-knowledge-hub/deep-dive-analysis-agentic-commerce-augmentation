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


PORTABILITY_CONTRACT_VERSION: Final = "workflow-portability.v3"


class PortabilityOperation(str, Enum):
    START_WORKFLOW = "start_workflow"
    PAUSE_WORKFLOW = "pause_workflow"
    RESUME_WORKFLOW = "resume_workflow"
    ASSIGN_ATTEMPT = "assign_attempt"
    HEARTBEAT_ATTEMPT = "heartbeat_attempt"
    COMMIT_EFFECT = "commit_effect"
    COMMIT_GRAPH_REVISION = "commit_graph_revision"
    RECORD_TASK_OUTCOME = "record_task_outcome"
    COMPLETE_WORKFLOW = "complete_workflow"
    CANCEL_WORKFLOW = "cancel_workflow"


class PortabilityJoinPolicy(str, Enum):
    ALL = "all"
    ANY = "any"
    QUORUM = "quorum"


class PortabilityJoinState(str, Enum):
    WAITING = "waiting"
    SATISFIED = "satisfied"
    IMPOSSIBLE = "impossible"


class PortabilityTaskOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


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
class PortabilityTaskDefinition:
    task_id: str
    task_type: str

    def __post_init__(self) -> None:
        _require_nonempty_string(self.task_id, "task_id")
        _require_nonempty_string(self.task_type, "task_type")


@dataclass(frozen=True)
class PortabilityEdgeDefinition:
    from_task_id: str
    to_task_id: str
    join_group_id: str

    def __post_init__(self) -> None:
        _require_nonempty_string(self.from_task_id, "from_task_id")
        _require_nonempty_string(self.to_task_id, "to_task_id")
        _require_nonempty_string(self.join_group_id, "join_group_id")


@dataclass(frozen=True)
class PortabilityJoinDefinition:
    join_group_id: str
    target_task_id: str
    policy: PortabilityJoinPolicy
    quorum: int | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(self.join_group_id, "join_group_id")
        _require_nonempty_string(self.target_task_id, "target_task_id")
        if type(self.policy) is not PortabilityJoinPolicy:
            raise PortabilityContractError("join policy is unsupported")
        if self.policy is PortabilityJoinPolicy.QUORUM:
            if type(self.quorum) is not int or self.quorum < 1:
                raise PortabilityContractError("quorum join requires a positive quorum")
        elif self.quorum is not None:
            raise PortabilityContractError(
                "non-quorum join cannot carry a quorum value"
            )


@dataclass(frozen=True)
class PortabilityGraphRevision:
    revision: int
    parent_revision: int | None
    tasks: tuple[PortabilityTaskDefinition, ...]
    edges: tuple[PortabilityEdgeDefinition, ...]
    joins: tuple[PortabilityJoinDefinition, ...]

    def __post_init__(self) -> None:
        _validate_graph_revision(self)


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
    topology_revision: PortabilityGraphRevision | None = None
    task_outcome: PortabilityTaskOutcome | None = None
    result_hash: str | None = None

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
            PortabilityOperation.RECORD_TASK_OUTCOME,
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

        if self.operation is PortabilityOperation.COMMIT_GRAPH_REVISION:
            if type(self.topology_revision) is not PortabilityGraphRevision:
                raise PortabilityContractError(
                    "commit_graph_revision requires an exact topology revision"
                )
        elif self.topology_revision is not None:
            raise PortabilityContractError(
                f"{self.operation.value} cannot carry topology evidence"
            )

        if self.operation is PortabilityOperation.RECORD_TASK_OUTCOME:
            if type(self.task_outcome) is not PortabilityTaskOutcome:
                raise PortabilityContractError(
                    "record_task_outcome requires an exact task outcome"
                )
            if self.task_outcome is PortabilityTaskOutcome.SUCCEEDED:
                if not _is_sha256(self.result_hash):
                    raise PortabilityContractError(
                        "successful task outcome requires a result hash"
                    )
            elif self.result_hash is not None:
                raise PortabilityContractError(
                    "unsuccessful task outcome cannot carry a result hash"
                )
        elif self.task_outcome is not None or self.result_hash is not None:
            raise PortabilityContractError(
                f"{self.operation.value} cannot carry task outcome evidence"
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
    initial_topology: PortabilityGraphRevision
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
    initial_graph_revision: int
    graph_revision: int
    graph_tasks: tuple[tuple[str, str, int], ...]
    graph_edges: tuple[tuple[str, str, str, int], ...]
    graph_joins: tuple[tuple[str, str, str, int | None, int], ...]
    task_outcomes: tuple[tuple[str, str, str | None], ...]
    join_states: tuple[tuple[str, str], ...]
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
    initial_topology: PortabilityGraphRevision,
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
            "initial_topology": canonical_graph_revision_payload(initial_topology),
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
        }
    )


def canonical_event_payload(payload: dict[str, object]) -> str:
    return _canonical_json(payload)


def canonical_graph_revision_payload(
    revision: PortabilityGraphRevision,
) -> dict[str, object]:
    return {
        "edges": [asdict(edge) for edge in revision.edges],
        "joins": [
            {**asdict(join), "policy": join.policy.value} for join in revision.joins
        ],
        "parent_revision": revision.parent_revision,
        "revision": revision.revision,
        "tasks": [asdict(task) for task in revision.tasks],
    }


def portability_graph_revision_digest(revision: PortabilityGraphRevision) -> str:
    return _sha256_json(canonical_graph_revision_payload(revision))


def portability_graph_revision_from_payload(
    payload: object,
) -> PortabilityGraphRevision:
    if type(payload) is not dict or frozenset(payload) != frozenset(
        {"edges", "joins", "parent_revision", "revision", "tasks"}
    ):
        raise PortabilityContractError("graph revision payload fields are invalid")
    tasks = payload["tasks"]
    edges = payload["edges"]
    joins = payload["joins"]
    if type(tasks) is not list or type(edges) is not list or type(joins) is not list:
        raise PortabilityContractError("graph revision collections must be arrays")

    def exact(record: object, fields: frozenset[str], label: str) -> dict[str, object]:
        if type(record) is not dict or frozenset(record) != fields:
            raise PortabilityContractError(f"graph {label} payload fields are invalid")
        return record

    return PortabilityGraphRevision(
        revision=payload["revision"],
        parent_revision=payload["parent_revision"],
        tasks=tuple(
            PortabilityTaskDefinition(
                **exact(item, frozenset({"task_id", "task_type"}), "task")
            )
            for item in tasks
        ),
        edges=tuple(
            PortabilityEdgeDefinition(
                **exact(
                    item,
                    frozenset({"from_task_id", "to_task_id", "join_group_id"}),
                    "edge",
                )
            )
            for item in edges
        ),
        joins=tuple(
            PortabilityJoinDefinition(
                join_group_id=record["join_group_id"],
                target_task_id=record["target_task_id"],
                policy=PortabilityJoinPolicy(record["policy"]),
                quorum=record["quorum"],
            )
            for item in joins
            for record in (
                exact(
                    item,
                    frozenset({"join_group_id", "target_task_id", "policy", "quorum"}),
                    "join",
                ),
            )
        ),
    )


def default_portability_topology(revision: int = 1) -> PortabilityGraphRevision:
    return PortabilityGraphRevision(
        revision=revision,
        parent_revision=None,
        tasks=(PortabilityTaskDefinition("task-a", "portable-task"),),
        edges=(),
        joins=(),
    )


def require_portability_revision_successor(
    current: PortabilityGraphRevision,
    candidate: PortabilityGraphRevision,
) -> None:
    if (
        candidate.parent_revision != current.revision
        or candidate.revision != current.revision + 1
    ):
        raise PortabilityContractError(
            "graph revision must be the next child of the active revision"
        )
    current_tasks = {task.task_id: task for task in current.tasks}
    candidate_tasks = {task.task_id: task for task in candidate.tasks}
    if not current_tasks.items() <= candidate_tasks.items():
        raise PortabilityContractError(
            "graph revision cannot remove or rewrite existing tasks"
        )
    new_task_ids = set(candidate_tasks) - set(current_tasks)
    if not new_task_ids:
        raise PortabilityContractError("graph revision must add at least one task")
    if not set(current.edges) <= set(candidate.edges):
        raise PortabilityContractError("graph revision cannot remove existing edges")
    if not set(current.joins) <= set(candidate.joins):
        raise PortabilityContractError("graph revision cannot remove existing joins")
    if any(
        edge.to_task_id not in new_task_ids
        for edge in set(candidate.edges) - set(current.edges)
    ):
        raise PortabilityContractError(
            "graph revision cannot add prerequisites to existing tasks"
        )
    if any(
        join.target_task_id not in new_task_ids
        for join in set(candidate.joins) - set(current.joins)
    ):
        raise PortabilityContractError(
            "graph revision cannot add joins to existing tasks"
        )


def portability_join_states(
    revision: PortabilityGraphRevision,
    outcomes: dict[str, PortabilityTaskOutcome],
) -> tuple[tuple[str, PortabilityJoinState], ...]:
    predecessors: dict[str, tuple[str, ...]] = {
        join.join_group_id: tuple(
            edge.from_task_id
            for edge in revision.edges
            if edge.join_group_id == join.join_group_id
        )
        for join in revision.joins
    }
    states = []
    for join in revision.joins:
        task_ids = predecessors[join.join_group_id]
        successes = sum(
            outcomes.get(task_id) is PortabilityTaskOutcome.SUCCEEDED
            for task_id in task_ids
        )
        pending = sum(task_id not in outcomes for task_id in task_ids)
        required = {
            PortabilityJoinPolicy.ALL: len(task_ids),
            PortabilityJoinPolicy.ANY: 1,
            PortabilityJoinPolicy.QUORUM: int(join.quorum or 0),
        }[join.policy]
        if successes >= required:
            state = PortabilityJoinState.SATISFIED
        elif successes + pending < required:
            state = PortabilityJoinState.IMPOSSIBLE
        else:
            state = PortabilityJoinState.WAITING
        states.append((join.join_group_id, state))
    return tuple(states)


def portability_task_is_schedulable(
    revision: PortabilityGraphRevision,
    task_id: str,
    outcomes: dict[str, PortabilityTaskOutcome],
) -> bool:
    if task_id not in {task.task_id for task in revision.tasks} or task_id in outcomes:
        return False
    target_joins = tuple(
        join for join in revision.joins if join.target_task_id == task_id
    )
    if not target_joins:
        return True
    states = dict(portability_join_states(revision, outcomes))
    return all(
        states[join.join_group_id] is PortabilityJoinState.SATISFIED
        for join in target_joins
    )


def _validate_graph_revision(revision: PortabilityGraphRevision) -> None:
    if type(revision.revision) is not int or revision.revision < 1:
        raise PortabilityContractError("graph revision must be positive")
    if revision.parent_revision is not None and (
        type(revision.parent_revision) is not int
        or revision.parent_revision < 1
        or revision.parent_revision >= revision.revision
    ):
        raise PortabilityContractError("graph parent revision is invalid")
    if type(revision.tasks) is not tuple or not revision.tasks:
        raise PortabilityContractError("graph tasks must be a non-empty tuple")
    if type(revision.edges) is not tuple or type(revision.joins) is not tuple:
        raise PortabilityContractError("graph edges and joins must be tuples")
    if any(type(task) is not PortabilityTaskDefinition for task in revision.tasks):
        raise PortabilityContractError("graph task must use the exact contract")
    if any(type(edge) is not PortabilityEdgeDefinition for edge in revision.edges):
        raise PortabilityContractError("graph edge must use the exact contract")
    if any(type(join) is not PortabilityJoinDefinition for join in revision.joins):
        raise PortabilityContractError("graph join must use the exact contract")
    if revision.tasks != tuple(sorted(revision.tasks, key=lambda item: item.task_id)):
        raise PortabilityContractError("graph tasks must be canonically ordered")
    if revision.edges != tuple(
        sorted(
            revision.edges,
            key=lambda item: (
                item.to_task_id,
                item.join_group_id,
                item.from_task_id,
            ),
        )
    ):
        raise PortabilityContractError("graph edges must be canonically ordered")
    if revision.joins != tuple(
        sorted(revision.joins, key=lambda item: item.join_group_id)
    ):
        raise PortabilityContractError("graph joins must be canonically ordered")
    task_ids = [task.task_id for task in revision.tasks]
    if len(task_ids) != len(set(task_ids)):
        raise PortabilityContractError("graph task identity is duplicated")
    join_ids = [join.join_group_id for join in revision.joins]
    if len(join_ids) != len(set(join_ids)):
        raise PortabilityContractError("graph join identity is duplicated")
    if len({join.target_task_id for join in revision.joins}) != len(revision.joins):
        raise PortabilityContractError("graph task cannot own multiple join groups")
    known_tasks = set(task_ids)
    known_joins = {join.join_group_id: join for join in revision.joins}
    edge_keys: set[tuple[str, str, str]] = set()
    adjacency = {task_id: set() for task_id in task_ids}
    for edge in revision.edges:
        if type(edge) is not PortabilityEdgeDefinition:
            raise PortabilityContractError("graph edge must use the exact contract")
        if (
            edge.from_task_id not in known_tasks
            or edge.to_task_id not in known_tasks
            or edge.from_task_id == edge.to_task_id
        ):
            raise PortabilityContractError("graph edge references invalid tasks")
        join = known_joins.get(edge.join_group_id)
        if join is None or join.target_task_id != edge.to_task_id:
            raise PortabilityContractError("graph edge does not bind its join")
        key = (edge.from_task_id, edge.to_task_id, edge.join_group_id)
        if key in edge_keys:
            raise PortabilityContractError("graph edge is duplicated")
        edge_keys.add(key)
        adjacency[edge.from_task_id].add(edge.to_task_id)
    for join in revision.joins:
        if type(join) is not PortabilityJoinDefinition:
            raise PortabilityContractError("graph join must use the exact contract")
        predecessors = {
            edge.from_task_id
            for edge in revision.edges
            if edge.join_group_id == join.join_group_id
        }
        if not predecessors:
            raise PortabilityContractError("graph join requires predecessor edges")
        if join.policy is PortabilityJoinPolicy.QUORUM and int(join.quorum or 0) > len(
            predecessors
        ):
            raise PortabilityContractError("graph quorum exceeds predecessor count")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise PortabilityContractError("graph revision must be acyclic")
        if task_id in visited:
            return
        visiting.add(task_id)
        for successor in adjacency[task_id]:
            visit(successor)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in task_ids:
        visit(task_id)


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
    "PortabilityGraphRevision",
    "PortabilityEdgeDefinition",
    "PortabilityJoinDefinition",
    "PortabilityJoinPolicy",
    "PortabilityJoinState",
    "PortabilityOperation",
    "PortabilitySnapshot",
    "PortabilityTaskDefinition",
    "PortabilityTaskOutcome",
    "canonical_command_payload",
    "canonical_event_payload",
    "canonical_graph_revision_payload",
    "default_portability_topology",
    "portability_command_digest",
    "portability_graph_revision_digest",
    "portability_graph_revision_from_payload",
    "portability_history_digest",
    "portability_join_states",
    "portability_task_is_schedulable",
    "require_portability_revision_successor",
]
