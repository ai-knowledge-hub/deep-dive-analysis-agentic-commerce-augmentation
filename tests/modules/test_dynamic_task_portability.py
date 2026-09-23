from __future__ import annotations

import hashlib

import pytest

from application.services.workflow_portability import (
    DeterministicClock,
    DeterministicEffectSink,
    DurableHistoryPortabilityAdapterFactory,
    GraphStatePortabilityAdapterFactory,
    InternalKernelAdapter,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
    SQLitePortabilityAdapterFactory,
)
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityContractError,
    PortabilityEdgeDefinition,
    PortabilityFaultPoint,
    PortabilityGraphRevision,
    PortabilityJoinDefinition,
    PortabilityJoinPolicy,
    PortabilityOperation,
    PortabilityTaskDefinition,
    PortabilityTaskOutcome,
    default_portability_topology,
    portability_join_states,
    require_portability_revision_successor,
)


TENANT_ID = "tenant-dynamic"
WORKFLOW_ID = "workflow-dynamic"


@pytest.fixture(
    params=("internal", "sqlite", "graph", "durable"),
    ids=("internal", "sqlite", "graph", "durable"),
)
def adapter_factory(request: pytest.FixtureRequest, tmp_path):
    if request.param == "internal":
        return InternalKernelAdapter
    path = tmp_path / f"{request.param}.sqlite3"
    if request.param == "sqlite":
        return SQLitePortabilityAdapterFactory(path)
    if request.param == "graph":
        return GraphStatePortabilityAdapterFactory(path)
    return DurableHistoryPortabilityAdapterFactory(path)


def _command(command_id, operation, *, revision=1, **fields):
    return PortabilityCommand(
        command_id=command_id,
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        operation=operation,
        graph_revision=revision,
        **fields,
    )


def _expanded_topology(*, suffix: str = "") -> PortabilityGraphRevision:
    task_type = "portable-task" if not suffix else f"portable-task-{suffix}"
    return PortabilityGraphRevision(
        revision=2,
        parent_revision=1,
        tasks=tuple(
            PortabilityTaskDefinition(task_id, task_type)
            for task_id in (
                "task-a",
                "task-b",
                "task-c",
                "task-join-all",
                "task-join-any",
                "task-join-quorum",
            )
        ),
        edges=(
            PortabilityEdgeDefinition("task-a", "task-join-all", "join-all"),
            PortabilityEdgeDefinition("task-b", "task-join-all", "join-all"),
            PortabilityEdgeDefinition("task-c", "task-join-all", "join-all"),
            PortabilityEdgeDefinition("task-a", "task-join-any", "join-any"),
            PortabilityEdgeDefinition("task-b", "task-join-any", "join-any"),
            PortabilityEdgeDefinition("task-a", "task-join-quorum", "join-quorum"),
            PortabilityEdgeDefinition("task-b", "task-join-quorum", "join-quorum"),
            PortabilityEdgeDefinition("task-c", "task-join-quorum", "join-quorum"),
        ),
        joins=(
            PortabilityJoinDefinition(
                "join-all", "task-join-all", PortabilityJoinPolicy.ALL
            ),
            PortabilityJoinDefinition(
                "join-any", "task-join-any", PortabilityJoinPolicy.ANY
            ),
            PortabilityJoinDefinition(
                "join-quorum",
                "task-join-quorum",
                PortabilityJoinPolicy.QUORUM,
                2,
            ),
        ),
    )


def _create_running(adapter_factory, clock, sink):
    adapter = adapter_factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=sink,
    )
    adapter.apply(_command("start", PortabilityOperation.START_WORKFLOW))
    return adapter


def _assign(adapter, task_id: str, *, revision: int = 2):
    adapter.apply(
        _command(
            f"assign-{task_id}",
            PortabilityOperation.ASSIGN_ATTEMPT,
            revision=revision,
            task_id=task_id,
            attempt_id=f"attempt-{task_id}",
            worker_id=f"worker-{task_id}",
            fencing_token=1,
            lease_expires_at_tick=10,
        )
    )


def _outcome(adapter, task_id: str, outcome: PortabilityTaskOutcome):
    adapter.apply(
        _command(
            f"outcome-{task_id}",
            PortabilityOperation.RECORD_TASK_OUTCOME,
            revision=2,
            task_id=task_id,
            attempt_id=f"attempt-{task_id}",
            worker_id=f"worker-{task_id}",
            fencing_token=1,
            task_outcome=outcome,
            result_hash=(
                hashlib.sha256(task_id.encode()).hexdigest()
                if outcome is PortabilityTaskOutcome.SUCCEEDED
                else None
            ),
        )
    )


def test_dynamic_expansion_and_join_projection_survive_restore(
    adapter_factory, tmp_path
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    expansion = _command(
        "expand-2",
        PortabilityOperation.COMMIT_GRAPH_REVISION,
        topology_revision=_expanded_topology(),
    )
    receipt = adapter.apply(expansion)
    assert adapter.apply(expansion) == receipt

    for task_id, outcome in (
        ("task-a", PortabilityTaskOutcome.SUCCEEDED),
        ("task-b", PortabilityTaskOutcome.FAILED),
        ("task-c", PortabilityTaskOutcome.CANCELED),
    ):
        _assign(adapter, task_id)
        _outcome(adapter, task_id, outcome)

    snapshot = adapter.snapshot()
    assert snapshot.graph_revision == 2
    assert snapshot.join_states == (
        ("join-all", "impossible"),
        ("join-any", "satisfied"),
        ("join-quorum", "impossible"),
    )
    assert snapshot.task_outcomes == (
        (
            "task-a",
            "succeeded",
            hashlib.sha256(b"task-a").hexdigest(),
        ),
        ("task-b", "failed", None),
        ("task-c", "canceled", None),
    )
    _assign(adapter, "task-join-any")
    for task_id in ("task-join-all", "task-join-quorum"):
        with pytest.raises(PortabilityInvariantError, match="not schedulable"):
            _assign(adapter, task_id)

    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    restored = adapter_factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )
    assert restored.snapshot() == adapter.snapshot()


def test_concurrent_expansion_is_fenced_and_exact_retry_is_idempotent(
    adapter_factory,
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    winner = _command(
        "expand-winner",
        PortabilityOperation.COMMIT_GRAPH_REVISION,
        topology_revision=_expanded_topology(),
    )
    loser = _command(
        "expand-loser",
        PortabilityOperation.COMMIT_GRAPH_REVISION,
        topology_revision=_expanded_topology(suffix="other"),
    )
    receipt = adapter.apply(winner)
    assert adapter.apply(winner) == receipt
    with pytest.raises(PortabilityInvariantError, match="active revision"):
        adapter.apply(loser)


def test_multiple_graph_revisions_replay_in_committed_order(adapter_factory):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    revision_two = _expanded_topology()
    adapter.apply(
        _command(
            "expand-2",
            PortabilityOperation.COMMIT_GRAPH_REVISION,
            topology_revision=revision_two,
        )
    )
    revision_three = PortabilityGraphRevision(
        revision=3,
        parent_revision=2,
        tasks=(*revision_two.tasks, PortabilityTaskDefinition("task-z", "task")),
        edges=revision_two.edges,
        joins=revision_two.joins,
    )
    adapter.apply(
        _command(
            "expand-3",
            PortabilityOperation.COMMIT_GRAPH_REVISION,
            revision=2,
            topology_revision=revision_three,
        )
    )
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    restored = adapter_factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )
    assert restored.snapshot().graph_revision == 3
    assert restored.snapshot().graph_tasks[-1] == ("task-z", "task", 3)


def test_expansion_recovers_from_precommit_crash_without_duplicate_revision(
    adapter_factory,
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    expansion = _command(
        "expand-crash",
        PortabilityOperation.COMMIT_GRAPH_REVISION,
        topology_revision=_expanded_topology(),
    )
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(expansion, fault=PortabilityFaultPoint.BEFORE_EVENT_COMMIT)
    assert adapter.snapshot().graph_revision == 1
    adapter.apply(expansion)
    assert adapter.snapshot().graph_revision == 2
    assert [
        event.event_type
        for event in adapter.export_history().events
        if event.event_type == "graph_revision_committed"
    ] == ["graph_revision_committed"]


@pytest.mark.parametrize(
    "fault",
    (
        PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
        PortabilityFaultPoint.AFTER_RECEIPT_BEFORE_EVENT_COMMIT,
    ),
)
def test_executed_effect_reconciles_after_revision_advance_and_fresh_restore(
    adapter_factory,
    fault,
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    _assign(adapter, "task-a", revision=1)
    effect = _command(
        "effect-before-expansion",
        PortabilityOperation.COMMIT_EFFECT,
        task_id="task-a",
        attempt_id="attempt-task-a",
        worker_id="worker-task-a",
        fencing_token=1,
        effect_id="effect-before-expansion",
        payload_hash=hashlib.sha256(b"effect before expansion").hexdigest(),
    )
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(effect, fault=fault)

    adapter.apply(
        _command(
            "expand-after-effect",
            PortabilityOperation.COMMIT_GRAPH_REVISION,
            topology_revision=_expanded_topology(),
        )
    )
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    close = getattr(adapter, "close", None)
    if callable(close):
        close()
    restored = adapter_factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )

    restored.apply(effect)

    recovered = restored.export_history()
    assert recovered.graph_revision == 2
    assert (
        sink.execution_call_count(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            effect_id="effect-before-expansion",
        )
        == 1
    )
    assert (
        sum(
            receipt.effect_id == "effect-before-expansion"
            for receipt in recovered.effect_receipts
        )
        == 1
    )
    assert tuple(
        event.event_type
        for event in recovered.events
        if event.command_id == effect.command_id
    ) == ("effect_reconciled",)
    assert (
        sum(
            receipt.command_id == effect.command_id
            for receipt in recovered.command_receipts
        )
        == 1
    )


def test_unexecuted_effect_cannot_bypass_revision_fence(adapter_factory):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    _assign(adapter, "task-a", revision=1)
    adapter.apply(
        _command(
            "expand-before-effect",
            PortabilityOperation.COMMIT_GRAPH_REVISION,
            topology_revision=_expanded_topology(),
        )
    )
    stale_effect = _command(
        "stale-unexecuted-effect",
        PortabilityOperation.COMMIT_EFFECT,
        task_id="task-a",
        attempt_id="attempt-task-a",
        worker_id="worker-task-a",
        fencing_token=1,
        effect_id="stale-unexecuted-effect",
        payload_hash=hashlib.sha256(b"stale unexecuted effect").hexdigest(),
    )

    with pytest.raises(PortabilityInvariantError, match="active revision"):
        adapter.apply(stale_effect)

    assert (
        sink.actual_effect_count(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            effect_id="stale-unexecuted-effect",
        )
        == 0
    )


def test_cancel_fences_late_task_outcome(adapter_factory):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    adapter.apply(
        _command(
            "expand-2",
            PortabilityOperation.COMMIT_GRAPH_REVISION,
            topology_revision=_expanded_topology(),
        )
    )
    _assign(adapter, "task-a")
    adapter.apply(
        _command(
            "cancel",
            PortabilityOperation.CANCEL_WORKFLOW,
            revision=2,
        )
    )
    with pytest.raises(PortabilityInvariantError):
        _outcome(adapter, "task-a", PortabilityTaskOutcome.SUCCEEDED)
    assert adapter.snapshot().task_outcomes == ()


def test_task_outcome_fences_later_heartbeat_and_new_effect(adapter_factory):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    adapter = _create_running(adapter_factory, clock, sink)
    adapter.apply(
        _command(
            "expand-2",
            PortabilityOperation.COMMIT_GRAPH_REVISION,
            topology_revision=_expanded_topology(),
        )
    )
    _assign(adapter, "task-a")
    _outcome(adapter, "task-a", PortabilityTaskOutcome.SUCCEEDED)
    with pytest.raises(PortabilityInvariantError, match="completed task"):
        adapter.apply(
            _command(
                "heartbeat-late",
                PortabilityOperation.HEARTBEAT_ATTEMPT,
                revision=2,
                task_id="task-a",
                attempt_id="attempt-task-a",
                worker_id="worker-task-a",
                fencing_token=1,
                lease_expires_at_tick=11,
            )
        )
    with pytest.raises(PortabilityInvariantError, match="completed task"):
        adapter.apply(
            _command(
                "effect-late",
                PortabilityOperation.COMMIT_EFFECT,
                revision=2,
                task_id="task-a",
                attempt_id="attempt-task-a",
                worker_id="worker-task-a",
                fencing_token=1,
                effect_id="late-effect",
                payload_hash=hashlib.sha256(b"late effect").hexdigest(),
            )
        )
    assert (
        sink.actual_effect_count(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            effect_id="late-effect",
        )
        == 0
    )


def test_graph_revision_rejects_cycles_and_impossible_quorums():
    tasks = (
        PortabilityTaskDefinition("a", "task"),
        PortabilityTaskDefinition("b", "task"),
    )
    with pytest.raises(PortabilityContractError, match="acyclic"):
        PortabilityGraphRevision(
            1,
            None,
            tasks,
            (
                PortabilityEdgeDefinition("b", "a", "join-a"),
                PortabilityEdgeDefinition("a", "b", "join-b"),
            ),
            (
                PortabilityJoinDefinition("join-a", "a", PortabilityJoinPolicy.ALL),
                PortabilityJoinDefinition("join-b", "b", PortabilityJoinPolicy.ALL),
            ),
        )
    with pytest.raises(PortabilityContractError, match="quorum exceeds"):
        PortabilityGraphRevision(
            1,
            None,
            tasks,
            (PortabilityEdgeDefinition("a", "b", "join-b"),),
            (
                PortabilityJoinDefinition(
                    "join-b", "b", PortabilityJoinPolicy.QUORUM, 2
                ),
            ),
        )


def test_expansion_cannot_retrofit_prerequisites_onto_existing_task():
    with pytest.raises(PortabilityContractError, match="prerequisites"):
        require_portability_revision_successor(
            default_portability_topology(),
            PortabilityGraphRevision(
                revision=2,
                parent_revision=1,
                tasks=(
                    PortabilityTaskDefinition("source", "task"),
                    PortabilityTaskDefinition("task-a", "portable-task"),
                ),
                edges=(PortabilityEdgeDefinition("source", "task-a", "late-join"),),
                joins=(
                    PortabilityJoinDefinition(
                        "late-join", "task-a", PortabilityJoinPolicy.ALL
                    ),
                ),
            ),
        )


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    (
        ({}, ("waiting", "waiting", "waiting")),
        (
            {"task-a": PortabilityTaskOutcome.SUCCEEDED},
            ("waiting", "satisfied", "waiting"),
        ),
        (
            {
                "task-a": PortabilityTaskOutcome.SUCCEEDED,
                "task-b": PortabilityTaskOutcome.SUCCEEDED,
            },
            ("waiting", "satisfied", "satisfied"),
        ),
        (
            {
                "task-a": PortabilityTaskOutcome.SUCCEEDED,
                "task-b": PortabilityTaskOutcome.SUCCEEDED,
                "task-c": PortabilityTaskOutcome.SUCCEEDED,
            },
            ("satisfied", "satisfied", "satisfied"),
        ),
        (
            {
                "task-a": PortabilityTaskOutcome.FAILED,
                "task-b": PortabilityTaskOutcome.CANCELED,
                "task-c": PortabilityTaskOutcome.FAILED,
            },
            ("impossible", "impossible", "impossible"),
        ),
    ),
)
def test_all_any_and_quorum_states_are_deterministic(outcomes, expected):
    states = portability_join_states(_expanded_topology(), outcomes)
    assert tuple(state.value for _join_id, state in states) == expected
