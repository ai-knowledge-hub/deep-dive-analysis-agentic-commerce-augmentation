from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import sqlite3
from types import MappingProxyType

import pytest

from application.services.workflow_portability import (
    DeterministicClock,
    DeterministicEffectSink,
    GraphStatePortabilityAdapterFactory,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
    verify_portability_history,
)
from domain.workflow import graph_state
from domain.workflow.graph_state import (
    GraphNode,
    GraphNodeType,
    GraphTransition,
    SEQUENTIAL_GRAPH_DEFINITION,
    project_graph_state,
    require_graph_operation_route,
    verify_graph_definition,
)
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityFaultPoint,
    PortabilityOperation,
)


TENANT_ID = "tenant-graph-state"
WORKFLOW_ID = "workflow-graph-state"
PAYLOAD_HASH = hashlib.sha256(b"graph-state effect").hexdigest()
DEFINITION_HASH = verify_graph_definition(SEQUENTIAL_GRAPH_DEFINITION)


def _command(
    command_id: str,
    operation: PortabilityOperation,
    **overrides,
) -> PortabilityCommand:
    values = {
        "command_id": command_id,
        "tenant_id": TENANT_ID,
        "workflow_id": WORKFLOW_ID,
        "operation": operation,
    }
    values.update(overrides)
    return PortabilityCommand(**values)


def _assignment() -> PortabilityCommand:
    return _command(
        "command-assign",
        PortabilityOperation.ASSIGN_ATTEMPT,
        task_id="task-a",
        attempt_id="attempt-a1",
        worker_id="worker-a",
        fencing_token=1,
        lease_expires_at_tick=10,
    )


def _effect() -> PortabilityCommand:
    return _command(
        "command-effect",
        PortabilityOperation.COMMIT_EFFECT,
        task_id="task-a",
        attempt_id="attempt-a1",
        worker_id="worker-a",
        fencing_token=1,
        effect_id="effect-a",
        payload_hash=PAYLOAD_HASH,
    )


def _factory(tmp_path):
    return GraphStatePortabilityAdapterFactory(tmp_path / "graph-state.sqlite3")


def _create(factory, clock, sink):
    return factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=sink,
    )


def test_graph_definition_is_exact_versioned_and_unambiguous():
    assert len(DEFINITION_HASH) == 64

    with pytest.raises(PortabilityInvariantError, match="state version"):
        verify_graph_definition(
            replace(SEQUENTIAL_GRAPH_DEFINITION, state_version="unknown")
        )
    with pytest.raises(PortabilityInvariantError, match="unknown node"):
        verify_graph_definition(
            replace(
                SEQUENTIAL_GRAPH_DEFINITION,
                transitions=(
                    GraphTransition(
                        "planned", "event.workflow_started", "missing", "lifecycle"
                    ),
                ),
            )
        )
    with pytest.raises(PortabilityInvariantError, match="ambiguous"):
        verify_graph_definition(
            replace(
                SEQUENTIAL_GRAPH_DEFINITION,
                transitions=(
                    *SEQUENTIAL_GRAPH_DEFINITION.transitions,
                    GraphTransition(
                        "planned", "event.workflow_started", "running", "lifecycle"
                    ),
                ),
            )
        )

    for transition in (
        GraphTransition("planned", "event.unknown", "running", "lifecycle"),
        GraphTransition("planned", "event.workflow_started", "running", "unknown"),
    ):
        with pytest.raises(PortabilityInvariantError, match="identity is unknown"):
            verify_graph_definition(
                replace(SEQUENTIAL_GRAPH_DEFINITION, transitions=(transition,))
            )
    with pytest.raises(PortabilityInvariantError, match="does not support"):
        verify_graph_definition(
            replace(
                SEQUENTIAL_GRAPH_DEFINITION,
                transitions=(
                    GraphTransition(
                        "planned", "event.workflow_started", "running", "attempt"
                    ),
                ),
            )
        )


def test_graph_reducer_tracks_routes_and_portable_checkpoint_cursor(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create(_factory(tmp_path), clock, sink)

    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    adapter.apply(_assignment())
    adapter.apply(_command("command-pause", PortabilityOperation.PAUSE_WORKFLOW))
    adapter.apply(_command("command-resume", PortabilityOperation.RESUME_WORKFLOW))

    graph = adapter.graph_state()
    checkpoint = adapter.checkpoint()
    assert graph.current_node_id == "running"
    assert graph.workflow_status == "running"
    assert graph.reducer_counts == (("attempt", 1), ("lifecycle", 3))
    assert len(graph.reducer_input_hashes) == 4
    assert all(len(input_hash) == 64 for input_hash in graph.reducer_input_hashes)
    assert len(graph.reducer_outputs) == 4
    assert all(len(output.output_hash) == 64 for output in graph.reducer_outputs)
    assert json.loads(graph.reducer_outputs[1].output_json)["attempt"] == {
        "attempt_id": "attempt-a1",
        "fencing_token": 1,
        "lease_expires_at_tick": 10,
        "task_id": "task-a",
        "worker_id": "worker-a",
    }
    assert graph.visited_node_ids == (
        "planned",
        "running",
        "running",
        "paused",
        "running",
    )
    assert graph.event_sequence == checkpoint.event_sequence == 3
    assert graph.history_hash == checkpoint.history_hash


def test_canceled_effect_reconciliation_uses_terminal_preserving_route(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = _factory(tmp_path)
    adapter = _create(factory, clock, sink)
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    adapter.apply(_assignment())
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(
            _effect(),
            fault=PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
        )
    adapter.apply(_command("command-cancel", PortabilityOperation.CANCEL_WORKFLOW))
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    adapter.close()

    restored = factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )
    restored.apply(_effect())

    graph = restored.graph_state()
    assert graph.current_node_id == "canceled"
    assert graph.workflow_status == "canceled"
    assert graph.reducer_counts == (
        ("attempt", 1),
        ("effect", 1),
        ("lifecycle", 2),
    )
    effect_output = json.loads(graph.reducer_outputs[-1].output_json)
    assert effect_output["event_type"] == "effect_reconciled"
    assert effect_output["effect"]["effect_id"] == "effect-a"
    assert (
        sink.execution_call_count(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            effect_id="effect-a",
        )
        == 1
    )


def test_graph_restore_reconstructs_without_original_adapter_state(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = _factory(tmp_path)
    original = _create(factory, clock, sink)
    original.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    original.apply(_assignment())
    history = original.export_history()
    checkpoint = original.checkpoint()
    graph_before = original.graph_state()
    original.close()

    restored = factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )

    assert restored.export_history() == history
    assert restored.graph_state() == graph_before


def test_equivalent_command_histories_produce_identical_graph_state(tmp_path):
    adapters = []
    for name in ("first", "second"):
        factory = GraphStatePortabilityAdapterFactory(tmp_path / f"{name}.sqlite3")
        adapter = _create(factory, DeterministicClock(), DeterministicEffectSink())
        adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
        adapter.apply(_assignment())
        adapter.apply(_effect())
        adapter.apply(
            _command("command-complete", PortabilityOperation.COMPLETE_WORKFLOW)
        )
        adapters.append(adapter)

    assert adapters[0].export_history() == adapters[1].export_history()
    assert adapters[0].checkpoint() == adapters[1].checkpoint()
    assert adapters[0].graph_state() == adapters[1].graph_state()


def test_missing_route_fails_closed_against_verified_history(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create(_factory(tmp_path), clock, sink)
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    history = adapter.export_history()
    portable_snapshot = verify_portability_history(history)
    definition = replace(
        SEQUENTIAL_GRAPH_DEFINITION,
        transitions=tuple(
            transition
            for transition in SEQUENTIAL_GRAPH_DEFINITION.transitions
            if not (
                transition.source_node_id == "planned"
                and transition.condition_id == "event.workflow_started"
            )
        ),
    )

    with pytest.raises(PortabilityInvariantError, match="no deterministic"):
        project_graph_state(
            history,
            portable_snapshot,
            definition=definition,
            expected_definition_hash=verify_graph_definition(definition),
        )


def test_graph_projection_rejects_snapshot_scope_substitution(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create(_factory(tmp_path), clock, sink)
    history = adapter.export_history()
    snapshot = verify_portability_history(history)

    with pytest.raises(PortabilityInvariantError, match="does not bind"):
        project_graph_state(
            history,
            replace(snapshot, tenant_id="other-tenant"),
            expected_definition_hash=DEFINITION_HASH,
        )


def test_graph_node_contract_rejects_extensible_subclasses():
    class ExtendedGraphNode(GraphNode):
        pass

    with pytest.raises(PortabilityInvariantError, match="exact contract"):
        verify_graph_definition(
            replace(
                SEQUENTIAL_GRAPH_DEFINITION,
                nodes=(
                    ExtendedGraphNode("planned", GraphNodeType.ENTRY, "planned"),
                    *SEQUENTIAL_GRAPH_DEFINITION.nodes[1:],
                ),
            )
        )


def test_committed_and_reconciled_effect_conditions_execute_distinct_branches(
    tmp_path,
):
    committed = _create(
        GraphStatePortabilityAdapterFactory(tmp_path / "committed.sqlite3"),
        DeterministicClock(),
        DeterministicEffectSink(),
    )
    committed.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    committed.apply(_assignment())
    committed.apply(_effect())

    committed_output = json.loads(
        committed.graph_state().reducer_outputs[-1].output_json
    )
    assert committed_output["event_type"] == "effect_committed"

    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = GraphStatePortabilityAdapterFactory(tmp_path / "reconciled.sqlite3")
    interrupted = _create(factory, clock, sink)
    interrupted.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    interrupted.apply(_assignment())
    with pytest.raises(PortabilityInjectedCrash):
        interrupted.apply(
            _effect(), fault=PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT
        )
    history = interrupted.export_history()
    checkpoint = interrupted.checkpoint()
    interrupted.close()
    reconciled = factory.restore(
        history=history, checkpoint=checkpoint, clock=clock, effect_sink=sink
    )
    reconciled.apply(_effect())

    reconciled_output = json.loads(
        reconciled.graph_state().reducer_outputs[-1].output_json
    )
    assert reconciled_output["event_type"] == "effect_reconciled"
    assert committed_output != reconciled_output
    assert committed.graph_state().state_hash != reconciled.graph_state().state_hash


def test_definition_hash_is_required_for_projection_and_route_admission(tmp_path):
    adapter = _create(
        _factory(tmp_path), DeterministicClock(), DeterministicEffectSink()
    )
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    history = adapter.export_history()
    altered = replace(
        SEQUENTIAL_GRAPH_DEFINITION,
        transitions=tuple(
            replace(transition, target_node_id="paused")
            if transition.condition_id == "event.attempt_assigned"
            else transition
            for transition in SEQUENTIAL_GRAPH_DEFINITION.transitions
        ),
    )

    with pytest.raises(PortabilityInvariantError, match="definition hash changed"):
        project_graph_state(
            history,
            verify_portability_history(history),
            definition=altered,
            expected_definition_hash=DEFINITION_HASH,
        )
    with pytest.raises(PortabilityInvariantError, match="definition hash changed"):
        require_graph_operation_route(
            history,
            verify_portability_history(history),
            PortabilityOperation.ASSIGN_ATTEMPT,
            definition=altered,
            expected_definition_hash=DEFINITION_HASH,
        )


def test_changed_reducer_behavior_changes_definition_pin_and_blocks_restore(
    tmp_path, monkeypatch
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    database_path = tmp_path / "graph-state.sqlite3"
    factory = GraphStatePortabilityAdapterFactory(database_path)
    adapter = _create(factory, clock, sink)
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    adapter.apply(_assignment())
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    graph_before = adapter.graph_state()
    adapter.close()

    def changed_attempt_reducer(event_type, payload, target):
        return {
            "attempt": payload,
            "event_type": event_type,
            "semantic_change": True,
            "target_node_id": target.node_id,
            "workflow_status": target.workflow_status,
        }

    changed_reducers = dict(graph_state._REDUCER_FUNCTIONS)
    changed_reducers["attempt"] = changed_attempt_reducer
    monkeypatch.setattr(
        graph_state, "_REDUCER_FUNCTIONS", MappingProxyType(changed_reducers)
    )
    changed_hash = verify_graph_definition(SEQUENTIAL_GRAPH_DEFINITION)

    assert changed_hash != DEFINITION_HASH
    changed_projection = project_graph_state(
        history,
        verify_portability_history(history),
        expected_definition_hash=changed_hash,
    )
    assert changed_projection.state_hash != graph_before.state_hash
    with pytest.raises(PortabilityInvariantError, match="definition hash changed"):
        factory.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=sink,
        )
    with pytest.raises(PortabilityInvariantError, match="definition pin"):
        GraphStatePortabilityAdapterFactory(database_path).restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=sink,
        )


def test_route_admission_reconstructs_history_instead_of_trusting_projection(
    tmp_path, monkeypatch
):
    adapter = _create(
        _factory(tmp_path), DeterministicClock(), DeterministicEffectSink()
    )
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    forged = replace(
        adapter.graph_state(),
        tenant_id="other-tenant",
        current_node_id="paused",
        workflow_status="paused",
        event_sequence=999,
        history_hash="f" * 64,
        state_hash="f" * 64,
    )
    monkeypatch.setattr(adapter, "_project", lambda _history: forged)

    with pytest.raises(PortabilityInvariantError, match="workflow graph route"):
        adapter.apply(
            _command("command-resume-forged", PortabilityOperation.RESUME_WORKFLOW)
        )


def test_reducer_digest_rejects_behavior_hidden_in_external_dependency(monkeypatch):
    external_behavior = "changed"

    def dependent_attempt_reducer(event_type, payload, target):
        return {
            external_behavior: payload,
            "event_type": event_type,
            "target_node_id": target.node_id,
            "workflow_status": target.workflow_status,
        }

    changed_reducers = dict(graph_state._REDUCER_FUNCTIONS)
    changed_reducers["attempt"] = dependent_attempt_reducer
    monkeypatch.setattr(
        graph_state, "_REDUCER_FUNCTIONS", MappingProxyType(changed_reducers)
    )

    with pytest.raises(PortabilityInvariantError, match="self-contained"):
        verify_graph_definition(SEQUENTIAL_GRAPH_DEFINITION)


def test_reducer_digest_rejects_identical_code_with_different_captured_defaults(
    monkeypatch,
):
    def build_attempt_reducer(external_behavior):
        def reducer(event_type, payload, target, behavior=external_behavior):
            return {
                "attempt": payload,
                "behavior": behavior,
                "event_type": event_type,
                "target_node_id": target.node_id,
                "workflow_status": target.workflow_status,
            }

        return reducer

    first = build_attempt_reducer("first")
    second = build_attempt_reducer("second")
    target = GraphNode("running", GraphNodeType.EXECUTION, "running")

    assert first.__code__ is second.__code__
    assert first.__defaults__ == ("first",)
    assert second.__defaults__ == ("second",)
    assert first("attempt_assigned", {}, target) != second(
        "attempt_assigned", {}, target
    )
    for reducer in (first, second):
        changed_reducers = dict(graph_state._REDUCER_FUNCTIONS)
        changed_reducers["attempt"] = reducer
        monkeypatch.setattr(
            graph_state, "_REDUCER_FUNCTIONS", MappingProxyType(changed_reducers)
        )
        with pytest.raises(PortabilityInvariantError, match="default-free signature"):
            verify_graph_definition(SEQUENTIAL_GRAPH_DEFINITION)


def test_restore_rejects_same_identity_and_version_with_altered_definition(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    database_path = tmp_path / "graph-state.sqlite3"
    factory = GraphStatePortabilityAdapterFactory(database_path)
    adapter = _create(factory, clock, sink)
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    adapter.close()
    altered = replace(
        SEQUENTIAL_GRAPH_DEFINITION,
        transitions=tuple(
            replace(transition, target_node_id="paused")
            if transition.condition_id == "event.attempt_assigned"
            else transition
            for transition in SEQUENTIAL_GRAPH_DEFINITION.transitions
        ),
    )

    with pytest.raises(PortabilityInvariantError, match="definition pin"):
        GraphStatePortabilityAdapterFactory(database_path, definition=altered).restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=sink,
        )


def test_missing_definition_pin_blocks_checkpoint_before_checkpoint_write(tmp_path):
    factory = _factory(tmp_path)
    adapter = _create(factory, DeterministicClock(), DeterministicEffectSink())
    connection = sqlite3.connect(factory.database_path)
    connection.execute(
        "DROP TRIGGER portability_benchmark_graph_definitions_delete_immutable"
    )
    connection.execute(
        """
        DELETE FROM portability_benchmark_graph_definitions
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (TENANT_ID, WORKFLOW_ID),
    )
    connection.commit()
    before = connection.execute(
        "SELECT COUNT(*) FROM portability_benchmark_checkpoints"
    ).fetchone()[0]

    with pytest.raises(PortabilityInvariantError, match="definition pin"):
        adapter.checkpoint()

    after = connection.execute(
        "SELECT COUNT(*) FROM portability_benchmark_checkpoints"
    ).fetchone()[0]
    connection.close()
    assert after == before
