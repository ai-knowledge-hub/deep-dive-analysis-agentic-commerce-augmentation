from __future__ import annotations

from dataclasses import replace
from enum import Enum
import hashlib
import sqlite3

import pytest

import application.services.workflow_portability.sqlite_adapter as sqlite_adapter_module
import domain.workflow.durable_history as durable_history_module
from application.services.workflow_portability import (
    DeterministicClock,
    DeterministicEffectSink,
    DurableHistoryPortabilityAdapterFactory,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
)
from domain.workflow.durable_history import (
    DURABLE_HISTORY_DEFINITION,
    durable_history_record_hash,
    verify_durable_history_definition,
)
from domain.workflow.lifecycle import WorkflowStatus
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityFaultPoint,
    PortabilityOperation,
)


TENANT_ID = "tenant-durable-history"
WORKFLOW_ID = "workflow-durable-history"
PAYLOAD_HASH = hashlib.sha256(b"durable-history effect").hexdigest()


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
    return DurableHistoryPortabilityAdapterFactory(tmp_path / "durable-history.sqlite3")


def _running_adapter(factory, clock, sink):
    adapter = factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=sink,
    )
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    return adapter


def _records_for(adapter, command_id):
    return tuple(
        record
        for record in adapter._delegate.durable_history_records()
        if record.command_id == command_id
    )


def _rewrite_journal(factory, ordered_records):
    connection = sqlite3.connect(factory.database_path)
    connection.execute(
        "DROP TRIGGER portability_benchmark_durable_records_delete_immutable"
    )
    connection.execute("DROP TRIGGER portability_benchmark_durable_head_monotonic")
    connection.execute(
        """
        DELETE FROM portability_benchmark_durable_records
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (TENANT_ID, WORKFLOW_ID),
    )
    previous_hash = "0" * 64
    for sequence, record in enumerate(ordered_records):
        record_hash = durable_history_record_hash(
            sequence=sequence,
            batch_sequence=record.batch_sequence,
            record_type=record.record_type,
            command_id=record.command_id,
            evidence_hash=record.evidence_hash,
            previous_record_hash=previous_hash,
        )
        connection.execute(
            """
            INSERT INTO portability_benchmark_durable_records (
                tenant_id, workflow_id, sequence, batch_sequence, record_type, command_id,
                evidence_hash, previous_record_hash, record_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                TENANT_ID,
                WORKFLOW_ID,
                sequence,
                record.batch_sequence,
                record.record_type,
                record.command_id,
                record.evidence_hash,
                previous_hash,
                record_hash,
            ),
        )
        previous_hash = record_hash
    connection.execute(
        """
        UPDATE portability_benchmark_durable_heads
        SET record_count = ?, record_head_hash = ?
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (len(ordered_records), previous_hash, TENANT_ID, WORKFLOW_ID),
    )
    connection.commit()
    connection.close()


def test_durable_journal_exactly_records_commit_boundaries_and_hash_chain(tmp_path):
    adapter = _running_adapter(
        _factory(tmp_path), DeterministicClock(), DeterministicEffectSink()
    )
    adapter.apply(_assignment())
    adapter.apply(_effect())

    records = adapter._delegate.durable_history_records()
    state = adapter.durable_history_state()
    assert [record.batch_sequence for record in records] == [
        0,
        0,
        0,
        1,
        1,
        1,
        2,
        2,
        2,
        2,
    ]
    assert [
        record.record_type for record in _records_for(adapter, "command-effect")
    ] == [
        "command_admitted",
        "effect_receipt_committed",
        "event_committed",
        "command_receipt_committed",
    ]
    previous_hash = "0" * 64
    for sequence, record in enumerate(records):
        assert record.sequence == sequence
        assert record.previous_record_hash == previous_hash
        assert record.record_hash == durable_history_record_hash(
            sequence=sequence,
            batch_sequence=record.batch_sequence,
            record_type=record.record_type,
            command_id=record.command_id,
            evidence_hash=record.evidence_hash,
            previous_record_hash=previous_hash,
        )
        previous_hash = record.record_hash
    assert state.record_count == len(records) == 10
    assert state.record_head_hash == records[-1].record_hash
    assert len(state.state_hash) == 64


@pytest.mark.parametrize(
    ("fault", "expected_phases"),
    [
        (PortabilityFaultPoint.BEFORE_EFFECT, ("command_admitted",)),
        (
            PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
            ("command_admitted",),
        ),
        (
            PortabilityFaultPoint.AFTER_RECEIPT_BEFORE_EVENT_COMMIT,
            ("command_admitted", "effect_receipt_committed"),
        ),
        (
            PortabilityFaultPoint.AFTER_EVENT_COMMIT_BEFORE_ACK,
            (
                "command_admitted",
                "effect_receipt_committed",
                "event_committed",
                "command_receipt_committed",
            ),
        ),
    ],
)
def test_effect_crash_boundaries_restore_and_reconcile_without_reexecution(
    tmp_path, fault, expected_phases
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, clock, sink)
    adapter.apply(_assignment())
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(_effect(), fault=fault)

    assert (
        tuple(record.record_type for record in _records_for(adapter, "command-effect"))
        == expected_phases
    )
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
    assert tuple(
        record.record_type for record in _records_for(restored, "command-effect")
    ) == (
        "command_admitted",
        "effect_receipt_committed",
        "event_committed",
        "command_receipt_committed",
    )
    assert (
        sink.execution_call_count(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            effect_id="effect-a",
        )
        == 1
    )


def test_restore_reconciles_portable_commit_after_process_loss_before_journal(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, clock, sink)

    # Model process loss after the authoritative SQLite commit but before the
    # strategy journal gets its separate, reconstructable projection update.
    adapter._delegate.apply(_assignment())
    assert _records_for(adapter, "command-assign") == ()
    history = adapter._delegate.export_history()
    checkpoint = adapter._delegate.checkpoint()
    adapter.close()

    restored = factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )
    assert tuple(
        record.record_type for record in _records_for(restored, "command-assign")
    ) == (
        "command_admitted",
        "event_committed",
        "command_receipt_committed",
    )
    assert restored.snapshot().workflow_status == "running"


def test_restore_requires_exact_immutable_strategy_definition(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, clock, sink)
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    adapter.close()

    changed = DurableHistoryPortabilityAdapterFactory(
        factory.database_path,
        definition=replace(
            DURABLE_HISTORY_DEFINITION,
            record_contract_version="durable-history-records.v2",
        ),
    )
    with pytest.raises(PortabilityInvariantError, match="pin"):
        changed.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=sink,
        )
    assert len(verify_durable_history_definition()) == 64


def test_restore_rejects_changed_lifecycle_semantics_under_existing_pin(
    tmp_path, monkeypatch
):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, clock, sink)
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    original_hash = verify_durable_history_definition()
    adapter.close()

    original_predicate = durable_history_module.can_transition_workflow

    def changed_predicate(source, target):
        if source is WorkflowStatus.COMPLETED and target is WorkflowStatus.RUNNING:
            return True
        return original_predicate(source, target)

    monkeypatch.setattr(
        durable_history_module,
        "can_transition_workflow",
        changed_predicate,
    )
    assert verify_durable_history_definition() != original_hash

    with pytest.raises(PortabilityInvariantError, match="definition pin"):
        DurableHistoryPortabilityAdapterFactory(factory.database_path).restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=sink,
        )


def test_strategy_definition_binds_operation_schema(monkeypatch):
    original_hash = verify_durable_history_definition()
    changed_operation = Enum(
        "ChangedPortabilityOperation",
        {
            **{operation.name: operation.value for operation in PortabilityOperation},
            "RETRY_WORKFLOW": "retry_workflow",
        },
        type=str,
    )
    monkeypatch.setattr(
        durable_history_module,
        "PortabilityOperation",
        changed_operation,
    )

    assert verify_durable_history_definition() != original_hash


def test_journal_sync_rejects_cross_scope_evidence_before_mutation(tmp_path):
    adapter = _running_adapter(
        _factory(tmp_path), DeterministicClock(), DeterministicEffectSink()
    )
    records_before = adapter._delegate.durable_history_records()

    with pytest.raises(PortabilityInvariantError, match="scope or revision"):
        adapter._delegate.sync_durable_history(
            replace(adapter.export_history(), tenant_id="tenant-substituted")
        )

    assert adapter._delegate.durable_history_records() == records_before


def test_live_projection_rejects_coordinated_journal_corruption(tmp_path):
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, DeterministicClock(), DeterministicEffectSink())
    connection = sqlite3.connect(factory.database_path)
    connection.execute(
        "DROP TRIGGER portability_benchmark_durable_records_update_immutable"
    )
    connection.execute(
        """
        UPDATE portability_benchmark_durable_records
        SET record_hash = ?
        WHERE tenant_id = ? AND workflow_id = ? AND sequence = 0
        """,
        ("f" * 64, TENANT_ID, WORKFLOW_ID),
    )
    connection.commit()
    connection.close()

    with pytest.raises(PortabilityInvariantError, match="hash chain"):
        adapter.durable_history_state()


def test_reordered_rehashed_journal_is_rejected_even_with_coordinated_head(tmp_path):
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, DeterministicClock(), DeterministicEffectSink())
    adapter.apply(_assignment())
    records = adapter._delegate.durable_history_records()
    reordered = tuple(
        replace(record, batch_sequence=batch_sequence)
        for batch_sequence, record in enumerate(reversed(records))
    )
    _rewrite_journal(factory, reordered)

    with pytest.raises(PortabilityInvariantError, match="causal order"):
        adapter.durable_history_state()


def test_non_effect_atomic_commit_batch_cannot_be_interleaved(tmp_path):
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, DeterministicClock(), DeterministicEffectSink())
    adapter.apply(_assignment())
    records = {
        (record.command_id, record.record_type): record
        for record in adapter._delegate.durable_history_records()
    }
    subtle_identities = (
        ("command-start", "command_admitted"),
        ("command-assign", "command_admitted"),
        ("command-start", "event_committed"),
        ("command-start", "command_receipt_committed"),
        ("command-assign", "event_committed"),
        ("command-assign", "command_receipt_committed"),
    )
    subtle_permutation = tuple(
        replace(records[identity], batch_sequence=0 if index < 4 else 1)
        for index, identity in enumerate(subtle_identities)
    )
    _rewrite_journal(factory, subtle_permutation)

    with pytest.raises(PortabilityInvariantError, match="batch crosses commands"):
        adapter.durable_history_state()


def test_separate_batches_cannot_admit_command_before_prerequisite_commit(tmp_path):
    factory = _factory(tmp_path)
    adapter = _running_adapter(factory, DeterministicClock(), DeterministicEffectSink())
    adapter.apply(_assignment())
    records = {
        (record.command_id, record.record_type): record
        for record in adapter._delegate.durable_history_records()
    }
    premature_admission = (
        ("command-start", "command_admitted"),
        ("command-assign", "command_admitted"),
        ("command-start", "event_committed"),
        ("command-start", "command_receipt_committed"),
        ("command-assign", "event_committed"),
        ("command-assign", "command_receipt_committed"),
    )
    separate_batches = tuple(
        replace(
            records[identity],
            batch_sequence=(0, 1, 2, 2, 3, 3)[index],
        )
        for index, identity in enumerate(premature_admission)
    )
    _rewrite_journal(factory, separate_batches)

    with pytest.raises(
        PortabilityInvariantError,
        match="admission violates committed lifecycle prerequisites",
    ):
        adapter.durable_history_state()


def test_crash_split_non_effect_batch_can_complete_after_lifecycle_commands(tmp_path):
    adapter = _running_adapter(
        _factory(tmp_path), DeterministicClock(), DeterministicEffectSink()
    )
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(_assignment(), fault=PortabilityFaultPoint.BEFORE_EVENT_COMMIT)
    adapter.apply(_command("command-pause", PortabilityOperation.PAUSE_WORKFLOW))
    adapter.apply(_command("command-resume", PortabilityOperation.RESUME_WORKFLOW))
    adapter.apply(_assignment())

    assignment_records = _records_for(adapter, "command-assign")
    assert [record.record_type for record in assignment_records] == [
        "command_admitted",
        "event_committed",
        "command_receipt_committed",
    ]
    assert assignment_records[0].batch_sequence < assignment_records[1].batch_sequence
    assert assignment_records[1].batch_sequence == assignment_records[2].batch_sequence
    assert adapter.durable_history_state().workflow_status == "running"


def test_creation_rolls_back_workflow_pin_and_head_as_one_unit(tmp_path, monkeypatch):
    factory = _factory(tmp_path)
    original_insert = sqlite_adapter_module.insert_durable_history_identity

    def insert_then_crash(*args, **kwargs):
        original_insert(*args, **kwargs)
        raise RuntimeError("injected creation crash")

    monkeypatch.setattr(
        sqlite_adapter_module,
        "insert_durable_history_identity",
        insert_then_crash,
    )
    with pytest.raises(RuntimeError, match="creation crash"):
        factory.create(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            graph_revision=1,
            clock=DeterministicClock(),
            effect_sink=DeterministicEffectSink(),
        )

    connection = sqlite3.connect(factory.database_path)
    for table in (
        "portability_benchmark_workflows",
        "portability_benchmark_durable_definitions",
        "portability_benchmark_durable_heads",
    ):
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
    connection.close()

    monkeypatch.setattr(
        sqlite_adapter_module,
        "insert_durable_history_identity",
        original_insert,
    )
    adapter = factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=DeterministicClock(),
        effect_sink=DeterministicEffectSink(),
    )
    assert adapter.durable_history_state().record_count == 0
