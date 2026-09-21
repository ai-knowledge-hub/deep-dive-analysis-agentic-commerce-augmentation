"""Platform-owned deterministic graph state for the portability spike.

Graph state is a replayable execution projection. Portable commands, events,
receipts, and checkpoints remain authoritative and are verified independently
before this reducer is allowed to interpret them.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import inspect
import json
import textwrap
from types import MappingProxyType
from typing import Callable, Final

from domain.workflow.portability import (
    PortabilityHistory,
    PortabilityInvariantError,
    PortabilityOperation,
    PortabilitySnapshot,
)


GRAPH_STATE_CONTRACT_VERSION: Final = "workflow-graph-state.v1"
GRAPH_STATE_DEFINITION_ID: Final = "sequential-portability-graph.v1"


class GraphNodeType(str, Enum):
    ENTRY = "entry"
    EXECUTION = "execution"
    SUSPENSION = "suspension"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: GraphNodeType
    workflow_status: str


@dataclass(frozen=True)
class GraphTransition:
    source_node_id: str
    condition_id: str
    target_node_id: str
    reducer_id: str


@dataclass(frozen=True)
class GraphDefinition:
    definition_id: str
    state_version: str
    initial_node_id: str
    nodes: tuple[GraphNode, ...]
    transitions: tuple[GraphTransition, ...]


@dataclass(frozen=True)
class GraphConditionContract:
    condition_id: str
    event_type: str
    operation: PortabilityOperation


@dataclass(frozen=True)
class GraphReducerOutput:
    sequence: int
    reducer_id: str
    input_hash: str
    output_json: str
    output_hash: str


@dataclass(frozen=True)
class GraphReducerContract:
    reducer_id: str
    contract_version: str
    condition_ids: frozenset[str]


@dataclass(frozen=True)
class GraphStateProjection:
    state_version: str
    definition_id: str
    definition_hash: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    current_node_id: str
    workflow_status: str
    event_sequence: int
    history_hash: str
    reducer_counts: tuple[tuple[str, int], ...]
    reducer_input_hashes: tuple[str, ...]
    reducer_outputs: tuple[GraphReducerOutput, ...]
    visited_node_ids: tuple[str, ...]
    state_hash: str


SEQUENTIAL_GRAPH_DEFINITION: Final = GraphDefinition(
    definition_id=GRAPH_STATE_DEFINITION_ID,
    state_version=GRAPH_STATE_CONTRACT_VERSION,
    initial_node_id="planned",
    nodes=(
        GraphNode("planned", GraphNodeType.ENTRY, "planned"),
        GraphNode("running", GraphNodeType.EXECUTION, "running"),
        GraphNode("paused", GraphNodeType.SUSPENSION, "paused"),
        GraphNode("completed", GraphNodeType.TERMINAL, "completed"),
        GraphNode("canceled", GraphNodeType.TERMINAL, "canceled"),
    ),
    transitions=(
        GraphTransition("planned", "event.workflow_started", "running", "lifecycle"),
        GraphTransition("planned", "event.workflow_canceled", "canceled", "lifecycle"),
        GraphTransition("running", "event.workflow_paused", "paused", "lifecycle"),
        GraphTransition("running", "event.attempt_assigned", "running", "attempt"),
        GraphTransition("running", "event.attempt_heartbeat", "running", "attempt"),
        GraphTransition("running", "event.effect_committed", "running", "effect"),
        GraphTransition("running", "event.effect_reconciled", "running", "effect"),
        GraphTransition(
            "running", "event.workflow_completed", "completed", "lifecycle"
        ),
        GraphTransition("running", "event.workflow_canceled", "canceled", "lifecycle"),
        GraphTransition("paused", "event.workflow_resumed", "running", "lifecycle"),
        GraphTransition("paused", "event.workflow_canceled", "canceled", "lifecycle"),
        GraphTransition("canceled", "event.effect_reconciled", "canceled", "effect"),
    ),
)


_CONDITION_CONTRACTS: Final = tuple(
    GraphConditionContract(f"event.{event_type}", event_type, operation)
    for event_type, operation in (
        ("workflow_started", PortabilityOperation.START_WORKFLOW),
        ("workflow_paused", PortabilityOperation.PAUSE_WORKFLOW),
        ("workflow_resumed", PortabilityOperation.RESUME_WORKFLOW),
        ("attempt_assigned", PortabilityOperation.ASSIGN_ATTEMPT),
        ("attempt_heartbeat", PortabilityOperation.HEARTBEAT_ATTEMPT),
        ("effect_committed", PortabilityOperation.COMMIT_EFFECT),
        ("effect_reconciled", PortabilityOperation.COMMIT_EFFECT),
        ("workflow_completed", PortabilityOperation.COMPLETE_WORKFLOW),
        ("workflow_canceled", PortabilityOperation.CANCEL_WORKFLOW),
    )
)
_CONDITIONS_BY_ID: Final = MappingProxyType(
    {condition.condition_id: condition for condition in _CONDITION_CONTRACTS}
)


def _lifecycle_reducer(
    event_type: str, payload: dict[str, object], target: GraphNode
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "payload": payload,
        "target_node_id": target.node_id,
        "workflow_status": target.workflow_status,
    }


def _attempt_reducer(
    event_type: str, payload: dict[str, object], target: GraphNode
) -> dict[str, object]:
    return {
        "attempt": payload,
        "event_type": event_type,
        "target_node_id": target.node_id,
        "workflow_status": target.workflow_status,
    }


def _effect_reducer(
    event_type: str, payload: dict[str, object], target: GraphNode
) -> dict[str, object]:
    return {
        "effect": payload,
        "event_type": event_type,
        "target_node_id": target.node_id,
        "workflow_status": target.workflow_status,
    }


_REDUCER_CONTRACTS: Final = MappingProxyType(
    {
        contract.reducer_id: contract
        for contract in (
            GraphReducerContract(
                "attempt",
                "attempt-reducer.v1",
                frozenset({"event.attempt_assigned", "event.attempt_heartbeat"}),
            ),
            GraphReducerContract(
                "effect",
                "effect-reducer.v1",
                frozenset({"event.effect_committed", "event.effect_reconciled"}),
            ),
            GraphReducerContract(
                "lifecycle",
                "lifecycle-reducer.v1",
                frozenset(
                    {
                        "event.workflow_started",
                        "event.workflow_paused",
                        "event.workflow_resumed",
                        "event.workflow_completed",
                        "event.workflow_canceled",
                    }
                ),
            ),
        )
    }
)
_REDUCER_FUNCTIONS: Final[
    dict[str, Callable[[str, dict[str, object], GraphNode], dict[str, object]]]
] = MappingProxyType(
    {
        "attempt": _attempt_reducer,
        "effect": _effect_reducer,
        "lifecycle": _lifecycle_reducer,
    }
)


def verify_graph_definition(definition: GraphDefinition) -> str:
    """Validate and hash an exact graph contract without accepting extensions."""

    if type(definition) is not GraphDefinition:
        raise PortabilityInvariantError("graph definition must use the exact contract")
    if definition.state_version != GRAPH_STATE_CONTRACT_VERSION:
        raise PortabilityInvariantError("unsupported graph state version")
    if type(definition.definition_id) is not str or not definition.definition_id:
        raise PortabilityInvariantError("graph definition_id must be non-empty")
    if type(definition.initial_node_id) is not str or not definition.initial_node_id:
        raise PortabilityInvariantError("graph initial node must be non-empty")
    if type(definition.nodes) is not tuple or not definition.nodes:
        raise PortabilityInvariantError("graph nodes must be a non-empty tuple")
    if type(definition.transitions) is not tuple:
        raise PortabilityInvariantError("graph transitions must be a tuple")

    node_ids: set[str] = set()
    for node in definition.nodes:
        if type(node) is not GraphNode:
            raise PortabilityInvariantError("graph node must use the exact contract")
        if type(node.node_id) is not str or not node.node_id:
            raise PortabilityInvariantError("graph node_id must be non-empty")
        if type(node.node_type) is not GraphNodeType:
            raise PortabilityInvariantError("graph node type is unsupported")
        if type(node.workflow_status) is not str or not node.workflow_status:
            raise PortabilityInvariantError("graph node status must be non-empty")
        if node.node_id in node_ids:
            raise PortabilityInvariantError("graph node identity is duplicated")
        node_ids.add(node.node_id)
    if definition.initial_node_id not in node_ids:
        raise PortabilityInvariantError("graph initial node is unknown")

    transition_keys: set[tuple[str, str]] = set()
    event_routes: set[tuple[str, str]] = set()
    for transition in definition.transitions:
        if type(transition) is not GraphTransition:
            raise PortabilityInvariantError(
                "graph transition must use the exact contract"
            )
        if (
            transition.source_node_id not in node_ids
            or transition.target_node_id not in node_ids
        ):
            raise PortabilityInvariantError("graph transition references unknown node")
        if transition.condition_id not in _CONDITIONS_BY_ID:
            raise PortabilityInvariantError("graph condition identity is unknown")
        if transition.reducer_id not in _REDUCER_CONTRACTS:
            raise PortabilityInvariantError("graph reducer identity is unknown")
        if (
            transition.condition_id
            not in _REDUCER_CONTRACTS[transition.reducer_id].condition_ids
        ):
            raise PortabilityInvariantError(
                "graph reducer does not support transition condition"
            )
        key = (transition.source_node_id, transition.condition_id)
        if key in transition_keys:
            raise PortabilityInvariantError("graph transition route is ambiguous")
        transition_keys.add(key)
        event_key = (
            transition.source_node_id,
            _CONDITIONS_BY_ID[transition.condition_id].event_type,
        )
        if event_key in event_routes:
            raise PortabilityInvariantError("graph transition route is ambiguous")
        event_routes.add(event_key)

    return _sha256_json(
        {
            "definition_id": definition.definition_id,
            "condition_contracts": [
                {
                    **asdict(condition),
                    "operation": condition.operation.value,
                }
                for condition in _CONDITION_CONTRACTS
            ],
            "initial_node_id": definition.initial_node_id,
            "nodes": [
                {**asdict(node), "node_type": node.node_type.value}
                for node in definition.nodes
            ],
            "state_version": definition.state_version,
            "reducer_contracts": [
                {
                    "condition_ids": sorted(contract.condition_ids),
                    "contract_version": contract.contract_version,
                    "implementation_digest": _reducer_implementation_digest(
                        _REDUCER_FUNCTIONS[contract.reducer_id]
                    ),
                    "reducer_id": contract.reducer_id,
                }
                for contract in _REDUCER_CONTRACTS.values()
            ],
            "transitions": [
                asdict(transition) for transition in definition.transitions
            ],
        }
    )


def project_graph_state(
    history: PortabilityHistory,
    portable_snapshot: PortabilitySnapshot,
    *,
    definition: GraphDefinition = SEQUENTIAL_GRAPH_DEFINITION,
    expected_definition_hash: str,
) -> GraphStateProjection:
    """Rebuild graph traversal from history accepted by an independent oracle."""

    if (
        portable_snapshot.tenant_id != history.tenant_id
        or portable_snapshot.workflow_id != history.workflow_id
        or portable_snapshot.graph_revision != history.graph_revision
        or portable_snapshot.last_event_sequence != len(history.events) - 1
    ):
        raise PortabilityInvariantError(
            "portable snapshot does not bind the graph history"
        )
    definition_hash = verify_graph_definition(definition)
    if definition_hash != expected_definition_hash:
        raise PortabilityInvariantError("graph definition hash changed")
    nodes = {node.node_id: node for node in definition.nodes}
    current_node_id = definition.initial_node_id
    visited = [current_node_id]
    reducer_counts: dict[str, int] = {}
    reducer_input_hashes: list[str] = []
    reducer_outputs: list[GraphReducerOutput] = []

    for event in history.events:
        matching = tuple(
            transition
            for transition in definition.transitions
            if transition.source_node_id == current_node_id
            and _CONDITIONS_BY_ID[transition.condition_id].event_type
            == event.event_type
        )
        if len(matching) != 1:
            raise PortabilityInvariantError(
                "portable event has no deterministic graph transition"
            )
        transition = matching[0]
        reducer_counts[transition.reducer_id] = (
            reducer_counts.get(transition.reducer_id, 0) + 1
        )
        input_hash = _sha256_json(asdict(event))
        reducer_input_hashes.append(input_hash)
        payload = json.loads(event.payload_json)
        target = nodes[transition.target_node_id]
        output_json = _canonical_json(
            _REDUCER_FUNCTIONS[transition.reducer_id](event.event_type, payload, target)
        )
        reducer_outputs.append(
            GraphReducerOutput(
                sequence=event.sequence,
                reducer_id=transition.reducer_id,
                input_hash=input_hash,
                output_json=output_json,
                output_hash=hashlib.sha256(output_json.encode("utf-8")).hexdigest(),
            )
        )
        current_node_id = transition.target_node_id
        visited.append(current_node_id)

    node = nodes[current_node_id]
    if node.workflow_status != portable_snapshot.workflow_status:
        raise PortabilityInvariantError(
            "graph projection disagrees with portable lifecycle authority"
        )
    state_payload = {
        "definition_hash": definition_hash,
        "definition_id": definition.definition_id,
        "event_sequence": len(history.events) - 1,
        "graph_revision": history.graph_revision,
        "history_hash": history.history_hash,
        "node_id": current_node_id,
        "reducer_counts": sorted(reducer_counts.items()),
        "reducer_input_hashes": reducer_input_hashes,
        "reducer_outputs": [asdict(output) for output in reducer_outputs],
        "state_version": definition.state_version,
        "tenant_id": history.tenant_id,
        "visited_node_ids": visited,
        "workflow_id": history.workflow_id,
        "workflow_status": node.workflow_status,
    }
    return GraphStateProjection(
        state_version=definition.state_version,
        definition_id=definition.definition_id,
        definition_hash=definition_hash,
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
        graph_revision=history.graph_revision,
        current_node_id=current_node_id,
        workflow_status=node.workflow_status,
        event_sequence=len(history.events) - 1,
        history_hash=history.history_hash,
        reducer_counts=tuple(sorted(reducer_counts.items())),
        reducer_input_hashes=tuple(reducer_input_hashes),
        reducer_outputs=tuple(reducer_outputs),
        visited_node_ids=tuple(visited),
        state_hash=_sha256_json(state_payload),
    )


def require_graph_operation_route(
    history: PortabilityHistory,
    portable_snapshot: PortabilitySnapshot,
    operation: PortabilityOperation,
    *,
    definition: GraphDefinition = SEQUENTIAL_GRAPH_DEFINITION,
    expected_definition_hash: str,
) -> tuple[GraphTransition, ...]:
    """Reconstruct verified graph state before admitting a new command."""

    if type(operation) is not PortabilityOperation:
        raise PortabilityInvariantError("graph operation is unsupported")
    projection = project_graph_state(
        history,
        portable_snapshot,
        definition=definition,
        expected_definition_hash=expected_definition_hash,
    )
    routes = tuple(
        transition
        for transition in definition.transitions
        if transition.source_node_id == projection.current_node_id
        and _CONDITIONS_BY_ID[transition.condition_id].operation is operation
    )
    if not routes:
        raise PortabilityInvariantError(
            "command requires a running workflow graph route"
        )
    return routes


def _reducer_implementation_digest(reducer: object) -> str:
    """Hash canonical reducer syntax and reject hidden implementation inputs."""

    if not inspect.isfunction(reducer):
        raise PortabilityInvariantError("graph reducer implementation is unsupported")
    parameters = tuple(
        inspect.signature(reducer, follow_wrapped=False).parameters.values()
    )
    if (
        tuple(parameter.name for parameter in parameters)
        != ("event_type", "payload", "target")
        or any(
            parameter.kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in parameters
        )
        or reducer.__defaults__ is not None
        or reducer.__kwdefaults__ is not None
    ):
        raise PortabilityInvariantError(
            "graph reducer must have the exact default-free signature"
        )
    closure = inspect.getclosurevars(reducer)
    if closure.globals or closure.nonlocals or closure.builtins:
        raise PortabilityInvariantError(
            "graph reducer implementation must be self-contained"
        )
    try:
        syntax = ast.parse(textwrap.dedent(inspect.getsource(reducer)))
    except (OSError, TypeError, SyntaxError) as exc:
        raise PortabilityInvariantError(
            "graph reducer implementation source is unavailable"
        ) from exc
    functions = tuple(
        node
        for node in syntax.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    if len(functions) != 1 or isinstance(functions[0], ast.AsyncFunctionDef):
        raise PortabilityInvariantError("graph reducer implementation is unsupported")
    function = functions[0]
    function.name = "canonical_reducer"
    canonical_syntax = ast.dump(
        function, annotate_fields=True, include_attributes=False
    )
    return hashlib.sha256(canonical_syntax.encode("utf-8")).hexdigest()


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
    "GRAPH_STATE_CONTRACT_VERSION",
    "GRAPH_STATE_DEFINITION_ID",
    "GraphDefinition",
    "GraphConditionContract",
    "GraphNode",
    "GraphNodeType",
    "GraphReducerOutput",
    "GraphReducerContract",
    "GraphStateProjection",
    "GraphTransition",
    "SEQUENTIAL_GRAPH_DEFINITION",
    "project_graph_state",
    "require_graph_operation_route",
    "verify_graph_definition",
]
