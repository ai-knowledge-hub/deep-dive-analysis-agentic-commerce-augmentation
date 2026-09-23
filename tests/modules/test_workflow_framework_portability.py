from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from application.ports.workflow_portability import (
    WorkflowFrameworkAdapter,
    WorkflowFrameworkAdapterFactory,
)
from application.services.workflow_portability import (
    DeterministicClock,
    DeterministicEffectSink,
    DurableHistoryPortabilityAdapterFactory,
    GraphStatePortabilityAdapterFactory,
    InternalKernelAdapter,
    PortabilityConflictError,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
    SQLitePortabilityAdapterFactory,
    verify_portability_history,
)
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityContractError,
    PortabilityFaultPoint,
    PortabilityOperation,
    portability_history_digest,
)


TENANT_ID = "tenant-portability"
WORKFLOW_ID = "workflow-portability"
PAYLOAD_HASH = hashlib.sha256(b"bounded effect").hexdigest()


@pytest.fixture(
    params=["internal-kernel", "sqlite", "graph-state", "durable-history"],
    ids=["internal-kernel", "sqlite", "graph-state", "durable-history"],
)
def adapter_factory(
    request: pytest.FixtureRequest,
    tmp_path,
) -> WorkflowFrameworkAdapterFactory:
    """Register every candidate here to run the unchanged golden scenarios."""

    if request.param == "internal-kernel":
        return InternalKernelAdapter
    database_path = tmp_path / "portability-benchmark.sqlite3"
    if request.param == "sqlite":
        return SQLitePortabilityAdapterFactory(database_path)
    if request.param == "graph-state":
        return GraphStatePortabilityAdapterFactory(database_path)
    return DurableHistoryPortabilityAdapterFactory(database_path)


@pytest.fixture
def clock() -> DeterministicClock:
    return DeterministicClock()


@pytest.fixture
def effect_sink() -> DeterministicEffectSink:
    return DeterministicEffectSink()


def _command(
    command_id: str,
    operation: PortabilityOperation,
    **overrides,
) -> PortabilityCommand:
    payload = {
        "command_id": command_id,
        "tenant_id": TENANT_ID,
        "workflow_id": WORKFLOW_ID,
        "operation": operation,
    }
    payload.update(overrides)
    return PortabilityCommand(**payload)


def _create_adapter(
    adapter_factory: WorkflowFrameworkAdapterFactory,
    clock: DeterministicClock,
    effect_sink: DeterministicEffectSink,
) -> WorkflowFrameworkAdapter:
    return adapter_factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=effect_sink,
    )


def _running_adapter(
    adapter_factory: WorkflowFrameworkAdapterFactory,
    clock: DeterministicClock,
    effect_sink: DeterministicEffectSink,
) -> WorkflowFrameworkAdapter:
    adapter = _create_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    return adapter


def _assign_command(
    command_id: str = "command-assign",
    *,
    attempt_id: str = "attempt-a1",
    worker_id: str = "worker-a",
    fencing_token: int = 1,
    lease_expires_at_tick: int = 10,
) -> PortabilityCommand:
    return _command(
        command_id,
        PortabilityOperation.ASSIGN_ATTEMPT,
        task_id="task-a",
        attempt_id=attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        lease_expires_at_tick=lease_expires_at_tick,
    )


def _effect_command(
    command_id: str = "command-effect",
    *,
    attempt_id: str = "attempt-a1",
    worker_id: str = "worker-a",
    fencing_token: int = 1,
    effect_id: str = "effect-a",
) -> PortabilityCommand:
    return _command(
        command_id,
        PortabilityOperation.COMMIT_EFFECT,
        task_id="task-a",
        attempt_id=attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        effect_id=effect_id,
        payload_hash=PAYLOAD_HASH,
    )


def _history_with_hash(history, **changes):
    changed = replace(history, **changes)
    return replace(
        changed,
        history_hash=portability_history_digest(
            tenant_id=changed.tenant_id,
            workflow_id=changed.workflow_id,
            initial_topology=changed.initial_topology,
            graph_revision=changed.graph_revision,
            commands=changed.commands,
            events=changed.events,
            command_receipts=changed.command_receipts,
            effect_receipts=changed.effect_receipts,
        ),
    )


def test_contract_requires_worker_lease_identity_and_canonical_effect_hash():
    with pytest.raises(PortabilityContractError, match="worker_id"):
        _command(
            "command-assign",
            PortabilityOperation.ASSIGN_ATTEMPT,
            task_id="task-a",
            attempt_id="attempt-a",
            fencing_token=1,
            lease_expires_at_tick=10,
        )
    with pytest.raises(PortabilityContractError, match="lease expiry"):
        _assign_command(lease_expires_at_tick=0)
    with pytest.raises(PortabilityContractError, match="lowercase SHA-256"):
        replace(_effect_command(), payload_hash="not-a-digest")


def test_success_exports_commands_receipts_and_restores_without_live_store(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    adapter.apply(_effect_command())
    adapter.apply(_command("command-complete", PortabilityOperation.COMPLETE_WORKFLOW))
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()

    restored = adapter_factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=effect_sink,
    )

    assert restored.export_history() == history
    assert restored.snapshot() == verify_portability_history(history)
    assert restored.snapshot().workflow_status == "completed"
    assert len(history.commands) == 4
    assert len(history.command_receipts) == 4
    assert len(history.effect_receipts) == 1
    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )


def test_restored_store_does_not_share_lifecycle_mutations(
    adapter_factory, clock, effect_sink
):
    original = _running_adapter(adapter_factory, clock, effect_sink)
    history = original.export_history()
    restored = adapter_factory.restore(
        history=history,
        checkpoint=original.checkpoint(),
        clock=clock,
        effect_sink=effect_sink,
    )

    if restored.adapter_id in {
        "sqlite-portability.v1",
        "graph-state-portability.v1",
        "durable-history-portability.v1",
    }:
        original.close()
        assert restored.snapshot().workflow_status == "running"
        assert restored.export_history() == history
        with pytest.raises(PortabilityInvariantError, match="closed"):
            original.snapshot()
    else:
        original.apply(_command("command-cancel", PortabilityOperation.CANCEL_WORKFLOW))
        assert original.snapshot().workflow_status == "canceled"
        assert restored.snapshot().workflow_status == "running"
        assert restored.export_history() == history


def test_non_effect_crash_restores_pending_command_from_portable_evidence(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    command = _assign_command()
    with pytest.raises(PortabilityInjectedCrash) as crash:
        adapter.apply(command, fault=PortabilityFaultPoint.BEFORE_EVENT_COMMIT)
    assert crash.value.effect_executed is False
    history = adapter.export_history()
    assert command in history.commands
    assert all(event.command_id != command.command_id for event in history.events)

    restored = adapter_factory.restore(
        history=history,
        checkpoint=adapter.checkpoint(),
        clock=clock,
        effect_sink=effect_sink,
    )
    restored.apply(command)
    assert restored.snapshot().active_attempts == (
        ("task-a", "attempt-a1", "worker-a", 1, 10),
    )


@pytest.mark.parametrize(
    ("fault", "effect_count", "receipt_count", "event_count"),
    [
        (PortabilityFaultPoint.BEFORE_EFFECT, 0, 0, 0),
        (PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT, 1, 0, 0),
        (PortabilityFaultPoint.AFTER_RECEIPT_BEFORE_EVENT_COMMIT, 1, 1, 0),
        (PortabilityFaultPoint.BEFORE_EVENT_COMMIT, 1, 1, 0),
        (PortabilityFaultPoint.AFTER_EVENT_COMMIT_BEFORE_ACK, 1, 1, 1),
    ],
)
def test_effect_fault_matrix_uses_independent_sink_and_receipt_oracle(
    adapter_factory,
    clock,
    effect_sink,
    fault,
    effect_count,
    receipt_count,
    event_count,
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    command = _effect_command()

    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(command, fault=fault)
    history = adapter.export_history()
    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == effect_count
    )
    assert len(history.effect_receipts) == receipt_count
    assert (
        sum(event.command_id == command.command_id for event in history.events)
        == event_count
    )

    restored = adapter_factory.restore(
        history=history,
        checkpoint=adapter.checkpoint(),
        clock=clock,
        effect_sink=effect_sink,
    )
    restored.apply(command)

    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )
    assert (
        effect_sink.execution_call_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )
    assert len(restored.export_history().effect_receipts) == 1
    assert (
        sum(
            event.command_id == command.command_id
            for event in restored.export_history().events
        )
        == 1
    )


def test_unreceipted_execution_requires_its_exact_pending_command(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    command = _effect_command()
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(
            command,
            fault=PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
        )
    history = adapter.export_history()
    stripped_history = _history_with_hash(
        history,
        commands=tuple(
            recorded
            for recorded in history.commands
            if recorded.command_id != command.command_id
        ),
    )
    verify_portability_history(stripped_history)
    stripped_checkpoint = replace(
        adapter.checkpoint(),
        history_hash=stripped_history.history_hash,
    )

    with pytest.raises(PortabilityInvariantError, match="exact pending command"):
        adapter_factory.restore(
            history=stripped_history,
            checkpoint=stripped_checkpoint,
            clock=clock,
            effect_sink=effect_sink,
        )

    replacement = _command(
        "effect-replacement",
        PortabilityOperation.COMMIT_EFFECT,
        task_id="other-task",
        attempt_id="other-attempt",
        worker_id="other-worker",
        fencing_token=999,
        effect_id="effect-a",
        payload_hash=PAYLOAD_HASH,
    )
    with pytest.raises(PortabilityConflictError, match="execution provenance"):
        effect_sink.execute(replacement)
    assert (
        effect_sink.execution_call_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )


def test_lease_expiry_heartbeat_reassignment_and_late_worker_are_fenced(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command(lease_expires_at_tick=5))
    clock.advance(2)
    adapter.apply(
        _command(
            "command-heartbeat",
            PortabilityOperation.HEARTBEAT_ATTEMPT,
            task_id="task-a",
            attempt_id="attempt-a1",
            worker_id="worker-a",
            fencing_token=1,
            lease_expires_at_tick=8,
        )
    )
    with pytest.raises(PortabilityInvariantError, match="unexpired lease"):
        adapter.apply(
            _assign_command(
                "command-early-reassign",
                attempt_id="attempt-a2",
                worker_id="worker-b",
                fencing_token=2,
                lease_expires_at_tick=12,
            )
        )

    clock.advance(6)
    with pytest.raises(PortabilityInvariantError, match="expired lease"):
        adapter.apply(_effect_command(command_id="command-expired-effect"))
    adapter.apply(
        _assign_command(
            "command-reassign",
            attempt_id="attempt-a2",
            worker_id="worker-b",
            fencing_token=2,
            lease_expires_at_tick=15,
        )
    )
    with pytest.raises(PortabilityInvariantError, match="stale attempt"):
        adapter.apply(_effect_command(attempt_id="attempt-a1"))
    with pytest.raises(PortabilityInvariantError, match="stale worker"):
        adapter.apply(
            _command(
                "command-late-heartbeat",
                PortabilityOperation.HEARTBEAT_ATTEMPT,
                task_id="task-a",
                attempt_id="attempt-a1",
                worker_id="worker-a",
                fencing_token=1,
                lease_expires_at_tick=20,
            )
        )
    adapter.apply(
        _effect_command(
            command_id="command-current-effect",
            attempt_id="attempt-a2",
            worker_id="worker-b",
            fencing_token=2,
        )
    )
    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )


def test_pause_blocks_in_flight_effect_until_resume(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    adapter.apply(_command("command-pause", PortabilityOperation.PAUSE_WORKFLOW))

    with pytest.raises(PortabilityInvariantError, match="running workflow"):
        adapter.apply(_effect_command())
    adapter.apply(_command("command-resume", PortabilityOperation.RESUME_WORKFLOW))
    adapter.apply(_effect_command())

    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )


def test_cancellation_during_active_lease_blocks_late_completion_and_effect(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command(lease_expires_at_tick=10))
    adapter.apply(_command("command-cancel", PortabilityOperation.CANCEL_WORKFLOW))

    with pytest.raises(PortabilityInvariantError, match="running workflow"):
        adapter.apply(_effect_command())

    assert adapter.snapshot().workflow_status == "canceled"
    assert adapter.snapshot().active_attempts == (
        ("task-a", "attempt-a1", "worker-a", 1, 10),
    )
    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 0
    )


def test_cancellation_after_effect_reconciles_receipt_without_reexecution(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    command = _effect_command()
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(
            command,
            fault=PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
        )
    adapter.apply(_command("command-cancel", PortabilityOperation.CANCEL_WORKFLOW))
    history = adapter.export_history()

    restored = adapter_factory.restore(
        history=history,
        checkpoint=adapter.checkpoint(),
        clock=clock,
        effect_sink=effect_sink,
    )
    restored.apply(command)

    assert restored.snapshot().workflow_status == "canceled"
    assert len(restored.snapshot().committed_effects) == 1
    assert (
        effect_sink.execution_call_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )
    assert restored.export_history().events[-1].event_type == "effect_reconciled"


def test_changed_command_and_duplicate_effect_identity_fail_closed(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    assign = _assign_command()
    adapter.apply(assign)
    with pytest.raises(PortabilityConflictError, match="changed payload"):
        adapter.apply(replace(assign, worker_id="substituted-worker"))

    adapter.apply(_effect_command())
    before_conflict = adapter.export_history()
    with pytest.raises(PortabilityConflictError, match="already bound"):
        adapter.apply(_effect_command(command_id="different-command"))
    assert adapter.export_history() == before_conflict
    assert (
        effect_sink.actual_effect_count(
            tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID, effect_id="effect-a"
        )
        == 1
    )


def test_cross_scope_and_stale_revision_fail_before_state_change(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    before = adapter.export_history()
    with pytest.raises(PortabilityInvariantError, match="scope"):
        adapter.apply(replace(_assign_command(), tenant_id="other-tenant"))
    with pytest.raises(PortabilityInvariantError, match="graph revision"):
        adapter.apply(replace(_assign_command(), graph_revision=2))
    assert adapter.export_history() == before


def test_forged_command_and_effect_receipt_hashes_fail_after_digest_recompute(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    adapter.apply(_effect_command())
    history = adapter.export_history()

    command_receipts = (
        replace(history.command_receipts[0], request_hash="f" * 64),
        *history.command_receipts[1:],
    )
    forged_command_receipt = _history_with_hash(
        history, command_receipts=command_receipts
    )
    with pytest.raises(PortabilityInvariantError, match="request hash mismatch"):
        verify_portability_history(forged_command_receipt)

    effect_receipts = (replace(history.effect_receipts[0], request_hash="f" * 64),)
    forged_effect_receipt = _history_with_hash(history, effect_receipts=effect_receipts)
    with pytest.raises(PortabilityInvariantError, match="binding mismatch"):
        verify_portability_history(forged_effect_receipt)


def test_history_collections_require_canonical_cross_adapter_order(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    adapter.apply(_effect_command())
    adapter.apply(_effect_command(command_id="command-effect-b", effect_id="effect-b"))
    history = adapter.export_history()

    for field_name, message in (
        ("commands", "commands must be canonically ordered"),
        ("command_receipts", "command receipts must be canonically ordered"),
        ("effect_receipts", "effect receipts must be canonically ordered"),
    ):
        reordered = _history_with_hash(
            history,
            **{field_name: tuple(reversed(getattr(history, field_name)))},
        )
        with pytest.raises(PortabilityInvariantError, match=message):
            verify_portability_history(reordered)


def test_checkpoint_and_external_receipt_ledger_are_both_required_for_restore(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    adapter.apply(_effect_command())
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()

    with pytest.raises(PortabilityInvariantError, match="receipt inventory"):
        adapter_factory.restore(
            history=history,
            checkpoint=replace(checkpoint, committed_receipt_ids=()),
            clock=clock,
            effect_sink=effect_sink,
        )
    with pytest.raises(PortabilityInvariantError, match="receipt ledger"):
        adapter_factory.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=DeterministicEffectSink(),
        )


def test_coordinated_event_scope_and_payload_mutations_are_detected(
    adapter_factory, clock, effect_sink
):
    adapter = _running_adapter(adapter_factory, clock, effect_sink)
    adapter.apply(_assign_command())
    history = adapter.export_history()
    scoped_events = (
        replace(history.events[0], tenant_id="other-tenant"),
        history.events[1],
    )
    with pytest.raises(PortabilityInvariantError, match="scope"):
        verify_portability_history(_history_with_hash(history, events=scoped_events))

    expanded_events = (
        replace(history.events[0], payload_json='{"extra":true}'),
        history.events[1],
    )
    with pytest.raises(PortabilityInvariantError, match="fields"):
        verify_portability_history(_history_with_hash(history, events=expanded_events))

    substituted_assignment = replace(
        history.events[1],
        payload_json=(
            '{"attempt_id":"attempt-a1","fencing_token":1,'
            '"lease_expires_at_tick":10,"task_id":"task-substituted",'
            '"worker_id":"worker-a"}'
        ),
    )
    with pytest.raises(PortabilityInvariantError, match="does not match command"):
        verify_portability_history(
            _history_with_hash(
                history,
                events=(history.events[0], substituted_assignment),
            )
        )
