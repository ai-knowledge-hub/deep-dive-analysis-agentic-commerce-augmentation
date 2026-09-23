"""Isolated SQLite persistence candidate for the portability benchmark.

The schema in this module is deliberately separate from production migrations.
It persists platform-owned evidence in normalized records and uses SQLite only
as a candidate store; the independent clock and effect sink remain harness
authorities.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
from time import monotonic, sleep
from typing import Iterator

from application.ports.workflow_portability import (
    PortabilityClock,
    PortabilityEffectSink,
)
from application.services.workflow_portability.internal_kernel import (
    InternalKernelAdapter,
    InternalKernelStore,
    verify_portability_history,
)
from application.services.workflow_portability.replay import active_graph_revision
from application.services.workflow_portability.sqlite_graph_definition import (
    SQLiteGraphDefinitionStore,
)
from application.services.workflow_portability.sqlite_durable_history import (
    SQLiteDurableHistoryStore,
    insert_durable_history_identity,
)
from application.services.workflow_portability.sqlite_schema import SQLITE_SCHEMA
from application.services.workflow_portability.sqlite_schema_contract import (
    SQLITE_IMMUTABLE_TABLES,
)
from application.services.workflow_portability.sqlite_topology import (
    read_sqlite_graph_revision,
)
from domain.workflow.portability import (
    PORTABILITY_CONTRACT_VERSION,
    PortabilityCheckpoint,
    PortabilityCommand,
    PortabilityCommandReceipt,
    PortabilityConflictError,
    PortabilityEffectReceipt,
    PortabilityEvent,
    PortabilityFaultPoint,
    PortabilityGraphRevision,
    PortabilityHistory,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
    PortabilityOperation,
    PortabilitySnapshot,
    PortabilityTaskOutcome,
    canonical_graph_revision_payload,
    default_portability_topology,
    portability_history_digest,
)


_SQLITE_CONFIGURATION_TIMEOUT_SECONDS = 5.0
_SQLITE_CONFIGURATION_RETRY_SECONDS = 0.01


_IMMUTABLE_TABLES = SQLITE_IMMUTABLE_TABLES


class SQLitePortabilityAdapterFactory:
    """Factory bound to one isolated benchmark database path."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def create(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        initial_topology: PortabilityGraphRevision | None = None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> SQLitePortabilityAdapter:
        return SQLitePortabilityAdapter.create(
            database_path=self.database_path,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            initial_topology=initial_topology,
            clock=clock,
            effect_sink=effect_sink,
        )

    def restore(
        self,
        *,
        history: PortabilityHistory,
        checkpoint: PortabilityCheckpoint,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> SQLitePortabilityAdapter:
        return SQLitePortabilityAdapter.restore(
            database_path=self.database_path,
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=effect_sink,
        )

    def create_with_durable_history(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        initial_topology: PortabilityGraphRevision | None = None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
        strategy_id: str,
        state_version: str,
        definition_hash: str,
    ) -> SQLitePortabilityAdapter:
        return SQLitePortabilityAdapter.create_with_durable_history(
            database_path=self.database_path,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            initial_topology=initial_topology,
            clock=clock,
            effect_sink=effect_sink,
            strategy_id=strategy_id,
            state_version=state_version,
            definition_hash=definition_hash,
        )


class SQLitePortabilityAdapter(
    SQLiteGraphDefinitionStore,
    SQLiteDurableHistoryStore,
):
    adapter_id = "sqlite-portability.v1"

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        database_path: Path,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> None:
        self._connection = connection
        self.database_path = database_path
        self._tenant_id = tenant_id
        self._workflow_id = workflow_id
        self._graph_revision = graph_revision
        self._clock = clock
        self._effect_sink = effect_sink
        self._closed = False
        self.export_history()

    @classmethod
    def create(
        cls,
        *,
        database_path: str | Path,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int = 1,
        initial_topology: PortabilityGraphRevision | None = None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> SQLitePortabilityAdapter:
        return cls._create(
            database_path=database_path,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            initial_topology=initial_topology,
            clock=clock,
            effect_sink=effect_sink,
            durable_history_identity=None,
        )

    @classmethod
    def create_with_durable_history(
        cls,
        *,
        database_path: str | Path,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        initial_topology: PortabilityGraphRevision | None = None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
        strategy_id: str,
        state_version: str,
        definition_hash: str,
    ) -> SQLitePortabilityAdapter:
        return cls._create(
            database_path=database_path,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            initial_topology=initial_topology,
            clock=clock,
            effect_sink=effect_sink,
            durable_history_identity=(
                strategy_id,
                state_version,
                definition_hash,
            ),
        )

    @classmethod
    def _create(
        cls,
        *,
        database_path: str | Path,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        initial_topology: PortabilityGraphRevision | None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
        durable_history_identity: tuple[str, str, str] | None,
    ) -> SQLitePortabilityAdapter:
        validated = InternalKernelAdapter.create(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            initial_topology=initial_topology,
            clock=clock,
            effect_sink=effect_sink,
        )
        topology = initial_topology or default_portability_topology(graph_revision)
        path = Path(database_path)
        connection = _connect(path)
        try:
            _install_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO portability_benchmark_workflows (
                    tenant_id, workflow_id, graph_revision, initial_topology_json,
                    contract_version
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    workflow_id,
                    graph_revision,
                    _canonical_json(canonical_graph_revision_payload(topology)),
                    PORTABILITY_CONTRACT_VERSION,
                ),
            )
            if durable_history_identity is not None:
                strategy_id, state_version, definition_hash = durable_history_identity
                insert_durable_history_identity(
                    connection,
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    strategy_id=strategy_id,
                    state_version=state_version,
                    definition_hash=definition_hash,
                )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
            raise PortabilityConflictError(
                "SQLite portability workflow identity already exists"
            ) from exc
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
            raise
        del validated
        return cls(
            connection,
            database_path=path,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            clock=clock,
            effect_sink=effect_sink,
        )

    @classmethod
    def restore(
        cls,
        *,
        database_path: str | Path,
        history: PortabilityHistory,
        checkpoint: PortabilityCheckpoint,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> SQLitePortabilityAdapter:
        # Validate portable evidence and the independent provider ledger before
        # consulting candidate-native storage.
        InternalKernelAdapter.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=effect_sink,
        )
        path = Path(database_path)
        connection = _connect(path)
        try:
            _install_schema(connection)
            adapter = cls(
                connection,
                database_path=path,
                tenant_id=history.tenant_id,
                workflow_id=history.workflow_id,
                graph_revision=history.initial_topology.revision,
                clock=clock,
                effect_sink=effect_sink,
            )
            stored_history = adapter.export_history()
            if stored_history != history:
                raise PortabilityInvariantError(
                    "SQLite evidence does not match portable history"
                )
            adapter._require_stored_checkpoint(checkpoint)
            return adapter
        except Exception:
            connection.close()
            raise

    def close(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True

    def apply(
        self,
        command: PortabilityCommand,
        *,
        fault: PortabilityFaultPoint | None = None,
    ) -> PortabilityCommandReceipt:
        self._require_open()
        if command.operation is PortabilityOperation.COMMIT_EFFECT:
            already_committed = self._stage_effect_command(command)
            if fault is PortabilityFaultPoint.BEFORE_EFFECT and not already_committed:
                raise PortabilityInjectedCrash(
                    PortabilityFaultPoint.BEFORE_EFFECT,
                    effect_executed=False,
                )
        return self._apply_in_transaction(command, fault=fault)

    def _stage_effect_command(self, command: PortabilityCommand) -> bool:
        """Commit exact pending command evidence before any provider call."""

        with self._write_transaction(commit_injected_crash=True):
            history = self._read_history()
            if any(
                receipt.command_id == command.command_id
                for receipt in history.command_receipts
            ):
                return True
            if any(
                recorded.command_id == command.command_id
                for recorded in history.commands
            ):
                return False
            store = _store_from_history(history)
            candidate = InternalKernelAdapter(
                store,
                clock=self._clock,
                effect_sink=self._effect_sink,
            )
            try:
                candidate.apply(command, fault=PortabilityFaultPoint.BEFORE_EFFECT)
            except PortabilityInjectedCrash:
                self._persist_store(store)
                return False
            raise PortabilityInvariantError(
                "effect command staging reached provider execution"
            )

    def _apply_in_transaction(
        self,
        command: PortabilityCommand,
        *,
        fault: PortabilityFaultPoint | None,
    ) -> PortabilityCommandReceipt:
        with self._write_transaction(commit_injected_crash=True):
            history = self._read_history()
            store = _store_from_history(history)
            candidate = InternalKernelAdapter(
                store,
                clock=self._clock,
                effect_sink=self._effect_sink,
            )
            try:
                receipt = candidate.apply(command, fault=fault)
            except PortabilityInjectedCrash:
                self._persist_store(store)
                raise
            self._persist_store(store)
            return receipt

    def checkpoint(self) -> PortabilityCheckpoint:
        self._require_open()
        with self._write_transaction():
            history = self._read_history()
            candidate = InternalKernelAdapter(
                _store_from_history(history),
                clock=self._clock,
                effect_sink=self._effect_sink,
            )
            checkpoint = candidate.checkpoint()
            values = _checkpoint_values(checkpoint)
            self._connection.execute(
                """
                INSERT INTO portability_benchmark_checkpoints (
                    tenant_id, workflow_id, graph_revision, event_sequence,
                    history_hash, committed_receipt_ids_json, snapshot_json,
                    checkpoint_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, workflow_id, history_hash) DO NOTHING
                """,
                values,
            )
            stored = self._checkpoint_row(checkpoint.history_hash)
            if stored != values:
                raise PortabilityConflictError("SQLite checkpoint identity changed")
            return checkpoint

    def snapshot(self) -> PortabilitySnapshot:
        self._require_open()
        history = self.export_history()
        return verify_portability_history(history)

    def export_history(self) -> PortabilityHistory:
        self._require_open()
        history = self._read_history()
        verify_portability_history(history)
        sink_receipts = self._effect_sink.export_receipts(
            tenant_id=self._tenant_id,
            workflow_id=self._workflow_id,
        )
        if history.effect_receipts != sink_receipts:
            raise PortabilityInvariantError(
                "SQLite effect receipts do not match harness receipt ledger"
            )
        # Construction performs the independent provider-execution binding
        # checks, including exact pending-command reconciliation.
        InternalKernelAdapter(
            _store_from_history(history),
            clock=self._clock,
            effect_sink=self._effect_sink,
        )
        return history

    def evidence_counts(self) -> dict[str, int]:
        """Return stable measurement counters without exposing mutable rows."""

        self._require_open()
        tables = {
            "commands": "portability_benchmark_commands",
            "events": "portability_benchmark_events",
            "command_receipts": "portability_benchmark_command_receipts",
            "effect_receipts": "portability_benchmark_effect_receipts",
            "checkpoints": "portability_benchmark_checkpoints",
        }
        return {
            name: int(
                self._connection.execute(
                    f"""SELECT COUNT(*) FROM {table}
                    WHERE tenant_id = ? AND workflow_id = ?""",  # noqa: S608
                    (self._tenant_id, self._workflow_id),
                ).fetchone()[0]
            )
            for name, table in tables.items()
        }

    @property
    def journal_mode(self) -> str:
        self._require_open()
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0])

    @property
    def connection_settings(self) -> dict[str, object]:
        self._require_open()
        synchronous = int(self._connection.execute("PRAGMA synchronous").fetchone()[0])
        synchronous_names = {0: "off", 1: "normal", 2: "full", 3: "extra"}
        return {
            "busy_timeout_ms": int(
                self._connection.execute("PRAGMA busy_timeout").fetchone()[0]
            ),
            "foreign_keys": bool(
                self._connection.execute("PRAGMA foreign_keys").fetchone()[0]
            ),
            "journal_mode": self.journal_mode,
            "synchronous": synchronous_names.get(synchronous, str(synchronous)),
        }

    @contextmanager
    def _write_transaction(
        self, *, commit_injected_crash: bool = False
    ) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except PortabilityInjectedCrash:
            if commit_injected_crash:
                self._connection.commit()
            else:
                self._connection.rollback()
            raise
        except Exception:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def _persist_store(self, store: InternalKernelStore) -> None:
        try:
            for command_id in sorted(store.commands):
                command = store.commands[command_id]
                self._connection.execute(
                    """
                    INSERT INTO portability_benchmark_commands (
                        tenant_id, workflow_id, graph_revision, command_id,
                        operation, task_id, attempt_id, worker_id, fencing_token,
                        lease_expires_at_tick, effect_id, payload_hash,
                        topology_revision_json, task_outcome, result_hash,
                        request_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (tenant_id, workflow_id, command_id) DO NOTHING
                    """,
                    (
                        command.tenant_id,
                        command.workflow_id,
                        command.graph_revision,
                        command.command_id,
                        command.operation.value,
                        command.task_id,
                        command.attempt_id,
                        command.worker_id,
                        command.fencing_token,
                        command.lease_expires_at_tick,
                        command.effect_id,
                        command.payload_hash,
                        (
                            _canonical_json(
                                canonical_graph_revision_payload(
                                    command.topology_revision
                                )
                            )
                            if command.topology_revision is not None
                            else None
                        ),
                        (
                            command.task_outcome.value
                            if command.task_outcome is not None
                            else None
                        ),
                        command.result_hash,
                        _command_hash(command),
                    ),
                )
            persisted_event_count = int(
                self._connection.execute(
                    """
                    SELECT COUNT(*) FROM portability_benchmark_events
                    WHERE tenant_id = ? AND workflow_id = ?
                    """,
                    (self._tenant_id, self._workflow_id),
                ).fetchone()[0]
            )
            for event in store.events[persisted_event_count:]:
                self._connection.execute(
                    """
                    INSERT INTO portability_benchmark_events (
                        tenant_id, workflow_id, sequence, event_type,
                        command_id, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (tenant_id, workflow_id, sequence) DO NOTHING
                    """,
                    (
                        event.tenant_id,
                        event.workflow_id,
                        event.sequence,
                        event.event_type,
                        event.command_id,
                        event.payload_json,
                    ),
                )
            for command_id in sorted(store.command_receipts):
                receipt = store.command_receipts[command_id]
                self._connection.execute(
                    """
                    INSERT INTO portability_benchmark_command_receipts (
                        tenant_id, workflow_id, command_id, request_hash,
                        first_event_sequence, last_event_sequence
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (tenant_id, workflow_id, command_id) DO NOTHING
                    """,
                    (
                        self._tenant_id,
                        self._workflow_id,
                        receipt.command_id,
                        receipt.request_hash,
                        receipt.first_event_sequence,
                        receipt.last_event_sequence,
                    ),
                )
            for receipt in self._effect_sink.export_receipts(
                tenant_id=self._tenant_id,
                workflow_id=self._workflow_id,
            ):
                self._connection.execute(
                    """
                    INSERT INTO portability_benchmark_effect_receipts (
                        tenant_id, workflow_id, effect_id, command_id,
                        request_hash, graph_revision, task_id, attempt_id,
                        worker_id, fencing_token, payload_hash,
                        provider_receipt_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (tenant_id, workflow_id, effect_id) DO NOTHING
                    """,
                    (
                        receipt.tenant_id,
                        receipt.workflow_id,
                        receipt.effect_id,
                        receipt.command_id,
                        receipt.request_hash,
                        receipt.graph_revision,
                        receipt.task_id,
                        receipt.attempt_id,
                        receipt.worker_id,
                        receipt.fencing_token,
                        receipt.payload_hash,
                        receipt.provider_receipt_id,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise PortabilityConflictError(
                f"SQLite portability evidence conflict: {exc}"
            ) from exc

        persisted = self._read_history()
        expected = _history_from_store(
            store=store,
            effect_receipts=self._effect_sink.export_receipts(
                tenant_id=self._tenant_id,
                workflow_id=self._workflow_id,
            ),
        )
        if persisted != expected:
            raise PortabilityConflictError("SQLite immutable evidence changed")

    def _read_history(self) -> PortabilityHistory:
        workflow = self._connection.execute(
            """
            SELECT contract_version, initial_topology_json
            FROM portability_benchmark_workflows
            WHERE tenant_id = ? AND workflow_id = ? AND graph_revision = ?
            """,
            (self._tenant_id, self._workflow_id, self._graph_revision),
        ).fetchone()
        if workflow is None:
            raise PortabilityInvariantError("SQLite workflow identity is missing")
        if workflow[0] != PORTABILITY_CONTRACT_VERSION:
            raise PortabilityInvariantError("unsupported SQLite contract version")
        initial_topology = read_sqlite_graph_revision(workflow[1])
        if initial_topology.revision != self._graph_revision:
            raise PortabilityInvariantError(
                "SQLite initial topology does not match workflow identity"
            )

        commands = tuple(
            _command_from_row(row)
            for row in self._connection.execute(
                """
                SELECT command_id, tenant_id, workflow_id, operation,
                       graph_revision, task_id, attempt_id, worker_id,
                       fencing_token, lease_expires_at_tick, effect_id,
                       payload_hash, topology_revision_json, task_outcome,
                       result_hash, request_hash
                FROM portability_benchmark_commands
                WHERE tenant_id = ? AND workflow_id = ?
                ORDER BY command_id
                """,
                (self._tenant_id, self._workflow_id),
            )
        )
        events = tuple(
            PortabilityEvent(*row)
            for row in self._connection.execute(
                """
                SELECT sequence, tenant_id, workflow_id, event_type,
                       command_id, payload_json
                FROM portability_benchmark_events
                WHERE tenant_id = ? AND workflow_id = ?
                ORDER BY sequence
                """,
                (self._tenant_id, self._workflow_id),
            )
        )
        command_receipts = tuple(
            PortabilityCommandReceipt(*row)
            for row in self._connection.execute(
                """
                SELECT command_id, request_hash, first_event_sequence,
                       last_event_sequence
                FROM portability_benchmark_command_receipts
                WHERE tenant_id = ? AND workflow_id = ?
                ORDER BY command_id
                """,
                (self._tenant_id, self._workflow_id),
            )
        )
        effect_receipts = tuple(
            PortabilityEffectReceipt(*row)
            for row in self._connection.execute(
                """
                SELECT effect_id, command_id, request_hash, tenant_id,
                       workflow_id, graph_revision, task_id, attempt_id,
                       worker_id, fencing_token, payload_hash,
                       provider_receipt_id
                FROM portability_benchmark_effect_receipts
                WHERE tenant_id = ? AND workflow_id = ?
                ORDER BY effect_id
                """,
                (self._tenant_id, self._workflow_id),
            )
        )
        return _history(
            tenant_id=self._tenant_id,
            workflow_id=self._workflow_id,
            initial_topology=initial_topology,
            graph_revision=active_graph_revision(initial_topology, commands, events),
            commands=commands,
            events=events,
            command_receipts=command_receipts,
            effect_receipts=effect_receipts,
        )

    def _require_stored_checkpoint(self, checkpoint: PortabilityCheckpoint) -> None:
        if self._checkpoint_row(checkpoint.history_hash) != _checkpoint_values(
            checkpoint
        ):
            raise PortabilityInvariantError(
                "SQLite checkpoint evidence does not match portable checkpoint"
            )

    def _checkpoint_row(self, history_hash: str) -> tuple[object, ...] | None:
        row = self._connection.execute(
            """
            SELECT tenant_id, workflow_id, graph_revision, event_sequence,
                   history_hash, committed_receipt_ids_json, snapshot_json,
                   checkpoint_hash
            FROM portability_benchmark_checkpoints
            WHERE tenant_id = ? AND workflow_id = ? AND history_hash = ?
            """,
            (self._tenant_id, self._workflow_id, history_hash),
        ).fetchone()
        return tuple(row) if row is not None else None

    def _require_open(self) -> None:
        if self._closed:
            raise PortabilityInvariantError("SQLite portability adapter is closed")


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        path,
        timeout=5.0,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _install_schema(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing_objects = connection.execute(
            """
            SELECT 1 FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'
            LIMIT 1
            """
        ).fetchone()
        if existing_objects is None:
            for statement in _schema_statements():
                connection.execute(statement)
        _validate_schema_contract(connection)
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    _configure_connection(connection)


def _configure_connection(connection: sqlite3.Connection) -> None:
    """Apply post-validation settings with bounded SQLite lock handling."""

    deadline = monotonic() + _SQLITE_CONFIGURATION_TIMEOUT_SECONDS
    while True:
        try:
            journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()
        except sqlite3.OperationalError as exc:
            if not _is_sqlite_busy_or_locked(exc):
                raise PortabilityInvariantError(
                    "failed to configure SQLite portability journal mode"
                ) from exc
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise PortabilityInvariantError(
                    "SQLite portability journal configuration remained busy"
                ) from exc
            sleep(min(_SQLITE_CONFIGURATION_RETRY_SECONDS, remaining))
            continue
        if journal_mode is None or str(journal_mode[0]).lower() != "wal":
            raise PortabilityInvariantError(
                "SQLite portability journal mode is not WAL"
            )
        break
    connection.execute("PRAGMA synchronous = FULL")


def _is_sqlite_busy_or_locked(exc: sqlite3.OperationalError) -> bool:
    error_code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(error_code, int):
        base_code = error_code & 0xFF
        return base_code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return str(exc).lower() in {
        "database is locked",
        "database table is locked",
    }


@lru_cache(maxsize=1)
def _schema_statements() -> tuple[str, ...]:
    immutable_triggers = []
    for table in _IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            trigger = f"{table}_{operation.lower()}_immutable"
            immutable_triggers.append(
                f"""
                CREATE TRIGGER {trigger}
                BEFORE {operation} ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'portability benchmark evidence is immutable');
                END;
                """
            )
    script = "\n".join((SQLITE_SCHEMA, *immutable_triggers))
    statements = []
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statements.append(pending.strip())
            pending = ""
    if pending.strip():
        raise PortabilityInvariantError(
            "incomplete SQLite portability schema definition"
        )
    return tuple(statements)


def _validate_schema_contract(connection: sqlite3.Connection) -> None:
    try:
        actual = _schema_contract(connection)
    except sqlite3.Error as exc:
        raise PortabilityInvariantError(
            "unsupported SQLite portability schema contract"
        ) from exc
    if actual != _expected_schema_contract():
        raise PortabilityInvariantError(
            "unsupported SQLite portability schema contract"
        )


@lru_cache(maxsize=1)
def _expected_schema_contract() -> tuple[object, ...]:
    expected = sqlite3.connect(":memory:", isolation_level=None)
    try:
        expected.execute("PRAGMA foreign_keys = ON")
        expected.execute("BEGIN IMMEDIATE")
        for statement in _schema_statements():
            expected.execute(statement)
        expected.commit()
        return _schema_contract(expected)
    finally:
        expected.close()


def _schema_contract(connection: sqlite3.Connection) -> tuple[object, ...]:
    version_rows = tuple(
        connection.execute(
            """
            SELECT singleton, schema_version
            FROM portability_benchmark_schema
            ORDER BY singleton
            """
        )
    )
    table_names = tuple(
        str(row[0])
        for row in connection.execute(
            """
            SELECT name FROM sqlite_schema
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    )
    table_contracts = tuple(
        (
            table,
            _table_columns(connection, table),
            _table_unique_indexes(connection, table),
            _table_foreign_keys(connection, table),
        )
        for table in table_names
    )
    schema_objects = tuple(
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            _normalize_schema_sql(row[3]),
        )
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
    )
    return version_rows, table_contracts, schema_objects


def _table_columns(
    connection: sqlite3.Connection, table: str
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            f"PRAGMA table_info({_quote_identifier(table)})"  # noqa: S608
        )
    )


def _table_unique_indexes(
    connection: sqlite3.Connection, table: str
) -> tuple[tuple[object, ...], ...]:
    indexes = []
    index_rows = connection.execute(
        f"PRAGMA index_list({_quote_identifier(table)})"  # noqa: S608
    )
    for row in index_rows:
        if not int(row[2]):
            continue
        index_name = str(row[1])
        columns = tuple(
            str(column[2])
            for column in connection.execute(
                f"PRAGMA index_info({_quote_identifier(index_name)})"  # noqa: S608
            )
        )
        index_sql_row = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        indexes.append(
            (
                str(row[3]),
                int(row[4]),
                columns,
                _normalize_schema_sql(index_sql_row[0] if index_sql_row else None),
            )
        )
    return tuple(sorted(indexes, key=repr))


def _table_foreign_keys(
    connection: sqlite3.Connection, table: str
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                int(row[0]),
                int(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                str(row[6]),
                str(row[7]),
            )
            for row in connection.execute(
                f"PRAGMA foreign_key_list({_quote_identifier(table)})"  # noqa: S608
            )
        )
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _normalize_schema_sql(value: object) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())


def _command_hash(command: PortabilityCommand) -> str:
    from domain.workflow.portability import portability_command_digest

    return portability_command_digest(command)


def _command_from_row(row: tuple[object, ...]) -> PortabilityCommand:
    (
        command_id,
        tenant_id,
        workflow_id,
        operation,
        graph_revision,
        task_id,
        attempt_id,
        worker_id,
        fencing_token,
        lease_expires_at_tick,
        effect_id,
        payload_hash,
        topology_revision_json,
        task_outcome,
        result_hash,
        request_hash,
    ) = row
    command = PortabilityCommand(
        command_id=str(command_id),
        tenant_id=str(tenant_id),
        workflow_id=str(workflow_id),
        operation=PortabilityOperation(str(operation)),
        graph_revision=int(graph_revision),
        task_id=task_id,
        attempt_id=attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        lease_expires_at_tick=lease_expires_at_tick,
        effect_id=effect_id,
        payload_hash=payload_hash,
        topology_revision=(
            read_sqlite_graph_revision(topology_revision_json)
            if topology_revision_json is not None
            else None
        ),
        task_outcome=(
            PortabilityTaskOutcome(str(task_outcome))
            if task_outcome is not None
            else None
        ),
        result_hash=result_hash,
    )
    if request_hash != _command_hash(command):
        raise PortabilityInvariantError("SQLite command request hash mismatch")
    return command


def _history_from_store(
    *,
    store: InternalKernelStore,
    effect_receipts: tuple[PortabilityEffectReceipt, ...],
) -> PortabilityHistory:
    return _history(
        tenant_id=store.tenant_id,
        workflow_id=store.workflow_id,
        initial_topology=store.initial_topology,
        graph_revision=store.graph_revision,
        commands=tuple(store.commands[key] for key in sorted(store.commands)),
        events=tuple(store.events),
        command_receipts=tuple(
            store.command_receipts[key] for key in sorted(store.command_receipts)
        ),
        effect_receipts=effect_receipts,
    )


def _history(
    *,
    tenant_id: str,
    workflow_id: str,
    initial_topology: PortabilityGraphRevision,
    graph_revision: int,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
    command_receipts: tuple[PortabilityCommandReceipt, ...],
    effect_receipts: tuple[PortabilityEffectReceipt, ...],
) -> PortabilityHistory:
    return PortabilityHistory(
        contract_version=PORTABILITY_CONTRACT_VERSION,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        initial_topology=initial_topology,
        graph_revision=graph_revision,
        commands=commands,
        events=events,
        command_receipts=command_receipts,
        effect_receipts=effect_receipts,
        history_hash=portability_history_digest(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            initial_topology=initial_topology,
            graph_revision=graph_revision,
            commands=commands,
            events=events,
            command_receipts=command_receipts,
            effect_receipts=effect_receipts,
        ),
    )


def _store_from_history(history: PortabilityHistory) -> InternalKernelStore:
    return InternalKernelStore(
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
        initial_topology=history.initial_topology,
        graph_revision=history.graph_revision,
        commands={command.command_id: command for command in history.commands},
        events=list(history.events),
        command_receipts={
            receipt.command_id: receipt for receipt in history.command_receipts
        },
    )


def _checkpoint_values(checkpoint: PortabilityCheckpoint) -> tuple[object, ...]:
    receipt_json = _canonical_json(list(checkpoint.committed_receipt_ids))
    snapshot_json = _canonical_json(asdict(checkpoint.snapshot))
    checkpoint_payload = {
        "committed_receipt_ids": list(checkpoint.committed_receipt_ids),
        "contract_version": checkpoint.contract_version,
        "event_sequence": checkpoint.event_sequence,
        "graph_revision": checkpoint.graph_revision,
        "history_hash": checkpoint.history_hash,
        "snapshot": asdict(checkpoint.snapshot),
        "tenant_id": checkpoint.tenant_id,
        "workflow_id": checkpoint.workflow_id,
    }
    checkpoint_hash = hashlib.sha256(
        _canonical_json(checkpoint_payload).encode("utf-8")
    ).hexdigest()
    return (
        checkpoint.tenant_id,
        checkpoint.workflow_id,
        checkpoint.graph_revision,
        checkpoint.event_sequence,
        checkpoint.history_hash,
        receipt_json,
        snapshot_json,
        checkpoint_hash,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = ["SQLitePortabilityAdapter", "SQLitePortabilityAdapterFactory"]
