from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
from threading import Barrier, Event

import pytest

from application.services.workflow_portability import sqlite_adapter
from application.services.workflow_portability import (
    DeterministicClock,
    DeterministicEffectSink,
    PortabilityConflictError,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
    SQLitePortabilityAdapterFactory,
)
from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityFaultPoint,
    PortabilityOperation,
    portability_command_digest,
)


TENANT_ID = "tenant-sqlite-portability"
WORKFLOW_ID = "workflow-sqlite-portability"
PAYLOAD_HASH = hashlib.sha256(b"sqlite bounded effect").hexdigest()


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


def _assignment(
    command_id: str,
    *,
    attempt_id: str,
    worker_id: str,
    fencing_token: int,
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


def _running_factory(tmp_path):
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory = SQLitePortabilityAdapterFactory(tmp_path / "portability.sqlite3")
    adapter = factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=sink,
    )
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    return factory, adapter, clock, sink


def _second_connection(factory, adapter, clock, sink):
    history = adapter.export_history()
    checkpoint = adapter.checkpoint()
    return factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )


def _install_unconfigured_schema(database_path):
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN IMMEDIATE")
    for statement in sqlite_adapter._schema_statements():
        connection.execute(statement)
    connection.commit()
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    connection.close()


def test_restore_closes_original_connection_and_recovers_from_sqlite(tmp_path):
    factory, original, clock, sink = _running_factory(tmp_path)
    original.apply(
        _assignment(
            "command-assign",
            attempt_id="attempt-a1",
            worker_id="worker-a",
            fencing_token=1,
        )
    )
    history = original.export_history()
    checkpoint = original.checkpoint()
    original.close()

    restored = factory.restore(
        history=history,
        checkpoint=checkpoint,
        clock=clock,
        effect_sink=sink,
    )

    assert restored.export_history() == history
    restored.apply(_effect())
    assert restored.snapshot().committed_effects[0][0] == "effect-a"


def test_workflow_identity_rejects_a_second_active_revision(tmp_path):
    database_path = tmp_path / "portability.sqlite3"
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    first_factory = SQLitePortabilityAdapterFactory(database_path)
    first = first_factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=sink,
    )

    with pytest.raises(PortabilityConflictError, match="identity already exists"):
        SQLitePortabilityAdapterFactory(database_path).create(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            graph_revision=2,
            clock=clock,
            effect_sink=sink,
        )

    connection = sqlite3.connect(database_path)
    rows = connection.execute(
        """
        SELECT graph_revision FROM portability_benchmark_workflows
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (TENANT_ID, WORKFLOW_ID),
    ).fetchall()
    connection.close()
    assert rows == [(1,)]
    assert first.export_history().graph_revision == 1


def test_old_multiple_revision_identity_schema_fails_closed(tmp_path):
    database_path = tmp_path / "old-portability.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE portability_benchmark_workflows (
            tenant_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            graph_revision INTEGER NOT NULL,
            contract_version TEXT NOT NULL,
            PRIMARY KEY (tenant_id, workflow_id, graph_revision)
        )
        """
    )
    connection.commit()
    connection.close()

    with pytest.raises(PortabilityInvariantError, match="schema contract"):
        SQLitePortabilityAdapterFactory(database_path).create(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            graph_revision=1,
            clock=DeterministicClock(),
            effect_sink=DeterministicEffectSink(),
        )


def test_partial_schema_is_rejected_before_schema_or_workflow_mutation(tmp_path):
    database_path = tmp_path / "partial-portability.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE portability_benchmark_schema (
            singleton INTEGER NOT NULL PRIMARY KEY,
            schema_version INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO portability_benchmark_schema VALUES (1, 1)"
    )
    connection.execute(
        """
        CREATE TABLE portability_benchmark_workflows (
            tenant_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            graph_revision INTEGER NOT NULL,
            contract_version TEXT NOT NULL,
            PRIMARY KEY (tenant_id, workflow_id)
        )
        """
    )
    connection.commit()
    before_journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    before = tuple(
        connection.execute(
            """
            SELECT type, name, tbl_name, sql FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
    )
    connection.close()

    with pytest.raises(PortabilityInvariantError, match="schema contract"):
        SQLitePortabilityAdapterFactory(database_path).create(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            graph_revision=1,
            clock=DeterministicClock(),
            effect_sink=DeterministicEffectSink(),
        )

    connection = sqlite3.connect(database_path)
    after = tuple(
        connection.execute(
            """
            SELECT type, name, tbl_name, sql FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
    )
    workflow_rows = connection.execute(
        "SELECT COUNT(*) FROM portability_benchmark_workflows"
    ).fetchone()[0]
    after_journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    connection.close()
    assert after == before
    assert workflow_rows == 0
    assert after_journal_mode == before_journal_mode


def test_fresh_database_records_exact_sqlite_schema_version(tmp_path):
    factory, adapter, _clock, _sink = _running_factory(tmp_path)
    adapter.close()
    connection = sqlite3.connect(factory.database_path)
    version_rows = connection.execute(
        "SELECT singleton, schema_version FROM portability_benchmark_schema"
    ).fetchall()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            "UPDATE portability_benchmark_schema SET schema_version = 1"
        )
    connection.close()
    assert version_rows == [(1, 1)]


def test_concurrent_first_open_accepts_distinct_workflow_identities(tmp_path):
    for sample in range(20):
        database_path = tmp_path / f"distinct-first-open-{sample}.sqlite3"
        barrier = Barrier(2)

        def create(workflow_id):
            barrier.wait()
            try:
                return SQLitePortabilityAdapterFactory(database_path).create(
                    tenant_id=TENANT_ID,
                    workflow_id=workflow_id,
                    graph_revision=1,
                    clock=DeterministicClock(),
                    effect_sink=DeterministicEffectSink(),
                )
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(
                executor.map(create, ("workflow-first-a", "workflow-first-b"))
            )

        assert not any(isinstance(outcome, Exception) for outcome in outcomes)
        for adapter in outcomes:
            adapter.close()


def test_concurrent_first_open_deduplicates_identical_workflow_identity(tmp_path):
    for sample in range(20):
        database_path = tmp_path / f"identical-first-open-{sample}.sqlite3"
        barrier = Barrier(2)

        def create(_delivery):
            barrier.wait()
            try:
                return SQLitePortabilityAdapterFactory(database_path).create(
                    tenant_id=TENANT_ID,
                    workflow_id=WORKFLOW_ID,
                    graph_revision=1,
                    clock=DeterministicClock(),
                    effect_sink=DeterministicEffectSink(),
                )
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(create, range(2)))

        conflicts = tuple(
            outcome
            for outcome in outcomes
            if isinstance(outcome, PortabilityConflictError)
        )
        winners = tuple(
            outcome for outcome in outcomes if not isinstance(outcome, Exception)
        )
        assert len(conflicts) == 1
        assert len(winners) == 1
        winners[0].close()


def test_journal_configuration_retries_across_competing_write_lock(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "journal-retry.sqlite3"
    _install_unconfigured_schema(database_path)
    blocker = sqlite3.connect(
        database_path, isolation_level=None, check_same_thread=False
    )
    blocker.execute("BEGIN IMMEDIATE")
    candidate = sqlite3.connect(
        database_path, timeout=0.001, isolation_level=None, check_same_thread=False
    )
    candidate.execute("PRAGMA busy_timeout = 1")
    retry_observed = Event()
    release_retry = Event()

    def hold_retry(_seconds):
        retry_observed.set()
        assert release_retry.wait(timeout=2)

    monkeypatch.setattr(sqlite_adapter, "sleep", hold_retry)
    with ThreadPoolExecutor(max_workers=1) as executor:
        configured = executor.submit(sqlite_adapter._configure_connection, candidate)
        assert retry_observed.wait(timeout=2)
        blocker.commit()
        release_retry.set()
        configured.result(timeout=2)

    assert candidate.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    candidate.close()
    blocker.close()


def test_journal_configuration_busy_exhaustion_is_a_domain_error(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "journal-busy.sqlite3"
    _install_unconfigured_schema(database_path)
    blocker = sqlite3.connect(database_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    candidate = sqlite3.connect(database_path, timeout=0.001, isolation_level=None)
    candidate.execute("PRAGMA busy_timeout = 1")
    monkeypatch.setattr(
        sqlite_adapter, "_SQLITE_CONFIGURATION_TIMEOUT_SECONDS", 0.0
    )

    with pytest.raises(PortabilityInvariantError, match="remained busy"):
        sqlite_adapter._configure_connection(candidate)

    candidate.close()
    blocker.rollback()
    blocker.close()


def test_duplicate_delivery_across_connections_has_one_durable_winner(tmp_path):
    factory, first, clock, sink = _running_factory(tmp_path)
    second = _second_connection(factory, first, clock, sink)
    barrier = Barrier(2)
    command = _assignment(
        "command-assign",
        attempt_id="attempt-a1",
        worker_id="worker-a",
        fencing_token=1,
    )

    def deliver(adapter):
        barrier.wait()
        return adapter.apply(command)

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = tuple(executor.map(deliver, (first, second)))

    assert receipts[0] == receipts[1]
    history = first.export_history()
    assert sum(item.command_id == command.command_id for item in history.events) == 1
    assert (
        sum(item.command_id == command.command_id for item in history.command_receipts)
        == 1
    )


def test_competing_lease_assignments_have_one_winner_and_one_loser(tmp_path):
    factory, first, clock, sink = _running_factory(tmp_path)
    second = _second_connection(factory, first, clock, sink)
    barrier = Barrier(2)
    commands = (
        _assignment(
            "command-assign-a",
            attempt_id="attempt-a1",
            worker_id="worker-a",
            fencing_token=1,
        ),
        _assignment(
            "command-assign-b",
            attempt_id="attempt-a2",
            worker_id="worker-b",
            fencing_token=2,
        ),
    )

    def assign(pair):
        adapter, command = pair
        barrier.wait()
        try:
            return adapter.apply(command)
        except PortabilityInvariantError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(assign, zip((first, second), commands)))

    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    loser = next(item for item in outcomes if isinstance(item, Exception))
    assert "unexpired lease" in str(loser)
    assert len(first.snapshot().active_attempts) == 1


def test_cancellation_racing_effect_preserves_the_committed_order(tmp_path):
    factory, first, clock, sink = _running_factory(tmp_path)
    first.apply(
        _assignment(
            "command-assign",
            attempt_id="attempt-a1",
            worker_id="worker-a",
            fencing_token=1,
        )
    )
    second = _second_connection(factory, first, clock, sink)
    barrier = Barrier(2)
    cancel = _command("command-cancel", PortabilityOperation.CANCEL_WORKFLOW)

    def apply_after_barrier(adapter, command):
        barrier.wait()
        try:
            return adapter.apply(command)
        except PortabilityInvariantError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        effect_future = executor.submit(apply_after_barrier, first, _effect())
        cancel_future = executor.submit(apply_after_barrier, second, cancel)
        effect_outcome = effect_future.result()
        cancel_outcome = cancel_future.result()

    assert not isinstance(cancel_outcome, Exception)
    assert first.snapshot().workflow_status == "canceled"
    effect_count = sink.actual_effect_count(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        effect_id="effect-a",
    )
    if isinstance(effect_outcome, Exception):
        assert "running workflow" in str(effect_outcome)
        assert effect_count == 0
        assert first.snapshot().committed_effects == ()
    else:
        assert effect_count == 1
        assert len(first.snapshot().committed_effects) == 1

    with pytest.raises(PortabilityInvariantError):
        first.apply(
            _command("command-late-complete", PortabilityOperation.COMPLETE_WORKFLOW)
        )


def test_effect_execution_recovers_after_connection_loss_without_second_call(
    tmp_path,
):
    factory, adapter, clock, sink = _running_factory(tmp_path)
    adapter.apply(
        _assignment(
            "command-assign",
            attempt_id="attempt-a1",
            worker_id="worker-a",
            fencing_token=1,
        )
    )
    with pytest.raises(PortabilityInjectedCrash):
        adapter.apply(
            _effect(),
            fault=PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
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

    assert (
        sink.execution_call_count(
            tenant_id=TENANT_ID,
            workflow_id=WORKFLOW_ID,
            effect_id="effect-a",
        )
        == 1
    )
    assert len(restored.export_history().effect_receipts) == 1


def test_pending_effect_command_is_durable_before_provider_execution(tmp_path):
    database_path = tmp_path / "portability.sqlite3"

    class InspectingSink(DeterministicEffectSink):
        command_was_durable = False

        def execute(self, command):
            connection = sqlite3.connect(database_path)
            row = connection.execute(
                """
                SELECT request_hash FROM portability_benchmark_commands
                WHERE tenant_id = ? AND workflow_id = ? AND command_id = ?
                """,
                (command.tenant_id, command.workflow_id, command.command_id),
            ).fetchone()
            connection.close()
            self.command_was_durable = row is not None
            return super().execute(command)

    clock = DeterministicClock()
    sink = InspectingSink()
    factory = SQLitePortabilityAdapterFactory(database_path)
    adapter = factory.create(
        tenant_id=TENANT_ID,
        workflow_id=WORKFLOW_ID,
        graph_revision=1,
        clock=clock,
        effect_sink=sink,
    )
    adapter.apply(_command("command-start", PortabilityOperation.START_WORKFLOW))
    adapter.apply(
        _assignment(
            "command-assign",
            attempt_id="attempt-a1",
            worker_id="worker-a",
            fencing_token=1,
        )
    )

    adapter.apply(_effect())

    assert sink.command_was_durable is True


def test_sqlite_evidence_scope_order_and_immutability_are_database_enforced(
    tmp_path,
):
    factory, adapter, _clock, _sink = _running_factory(tmp_path)
    database_path = factory.database_path
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            """
            UPDATE portability_benchmark_commands
            SET request_hash = ?
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            ("f" * 64, TENANT_ID, WORKFLOW_ID),
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            """
            DELETE FROM portability_benchmark_events
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            (TENANT_ID, WORKFLOW_ID),
        )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            """
            INSERT INTO portability_benchmark_commands (
                tenant_id, workflow_id, graph_revision, command_id, operation,
                request_hash
            ) VALUES (?, ?, 1, 'cross-scope', 'start_workflow', ?)
            """,
            ("other-tenant", WORKFLOW_ID, "f" * 64),
        )
    connection.rollback()

    existing_hash = connection.execute(
        """
        SELECT request_hash FROM portability_benchmark_commands
        WHERE tenant_id = ? AND workflow_id = ? AND command_id = 'command-start'
        """,
        (TENANT_ID, WORKFLOW_ID),
    ).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute(
            """
            INSERT INTO portability_benchmark_commands (
                tenant_id, workflow_id, graph_revision, command_id, operation,
                request_hash
            ) VALUES (?, ?, 1, 'command-start', 'start_workflow', ?)
            """,
            (TENANT_ID, WORKFLOW_ID, existing_hash),
        )
    connection.rollback()

    gap_command = _command(
        "command-gap",
        PortabilityOperation.CANCEL_WORKFLOW,
    )
    connection.execute(
        """
        INSERT INTO portability_benchmark_commands (
            tenant_id, workflow_id, graph_revision, command_id, operation,
            request_hash
        ) VALUES (?, ?, 1, ?, ?, ?)
        """,
        (
            TENANT_ID,
            WORKFLOW_ID,
            gap_command.command_id,
            gap_command.operation.value,
            portability_command_digest(gap_command),
        ),
    )
    with pytest.raises(sqlite3.IntegrityError, match="gap-free"):
        connection.execute(
            """
            INSERT INTO portability_benchmark_events (
                tenant_id, workflow_id, sequence, event_type, command_id,
                payload_json
            ) VALUES (?, ?, 99, 'workflow_canceled', ?, '{}')
            """,
            (TENANT_ID, WORKFLOW_ID, gap_command.command_id),
        )
    connection.rollback()
    connection.close()
    assert adapter.snapshot().workflow_status == "running"
