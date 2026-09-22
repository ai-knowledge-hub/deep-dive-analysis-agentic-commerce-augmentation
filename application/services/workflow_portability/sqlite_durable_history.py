"""Immutable durable-history journal for the SQLite portability store."""

from __future__ import annotations

import sqlite3

from domain.workflow.durable_history import (
    DurableHistoryHead,
    DurableHistoryRecord,
    durable_history_evidence,
    durable_history_record_hash,
)
from domain.workflow.portability import (
    PortabilityConflictError,
    PortabilityHistory,
    PortabilityInvariantError,
)


DURABLE_DEFINITION_TABLE = "portability_benchmark_durable_definitions"
DURABLE_HEAD_TABLE = "portability_benchmark_durable_heads"
DURABLE_RECORD_TABLE = "portability_benchmark_durable_records"
DURABLE_HISTORY_SCHEMA = f"""
CREATE TABLE {DURABLE_DEFINITION_TABLE} (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL CHECK (length(strategy_id) > 0),
    state_version TEXT NOT NULL CHECK (length(state_version) > 0),
    definition_hash TEXT NOT NULL CHECK (length(definition_hash) = 64),
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES portability_benchmark_workflows (tenant_id, workflow_id)
);

CREATE TABLE {DURABLE_RECORD_TABLE} (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    batch_sequence INTEGER NOT NULL CHECK (batch_sequence >= 0),
    record_type TEXT NOT NULL CHECK (length(record_type) > 0),
    command_id TEXT NOT NULL CHECK (length(command_id) > 0),
    evidence_hash TEXT NOT NULL CHECK (length(evidence_hash) = 64),
    previous_record_hash TEXT NOT NULL CHECK (length(previous_record_hash) = 64),
    record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
    PRIMARY KEY (tenant_id, workflow_id, sequence),
    UNIQUE (tenant_id, workflow_id, record_type, command_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES portability_benchmark_workflows (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id, command_id)
        REFERENCES portability_benchmark_commands (tenant_id, workflow_id, command_id)
);

CREATE TABLE {DURABLE_HEAD_TABLE} (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    record_head_hash TEXT NOT NULL CHECK (length(record_head_hash) = 64),
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES {DURABLE_DEFINITION_TABLE} (tenant_id, workflow_id)
);

CREATE TRIGGER portability_benchmark_durable_record_sequence_guard
BEFORE INSERT ON {DURABLE_RECORD_TABLE}
BEGIN
    SELECT CASE WHEN NEW.sequence != COALESCE((
        SELECT MAX(sequence) + 1 FROM {DURABLE_RECORD_TABLE}
        WHERE tenant_id = NEW.tenant_id AND workflow_id = NEW.workflow_id
    ), 0) THEN RAISE(ABORT, 'durable-history sequence must be gap-free') END;
END;

CREATE TRIGGER portability_benchmark_durable_head_delete_immutable
BEFORE DELETE ON {DURABLE_HEAD_TABLE}
BEGIN
    SELECT RAISE(ABORT, 'durable-history head is immutable by deletion');
END;

CREATE TRIGGER portability_benchmark_durable_head_monotonic
BEFORE UPDATE ON {DURABLE_HEAD_TABLE}
BEGIN
    SELECT CASE WHEN NEW.tenant_id != OLD.tenant_id
        OR NEW.workflow_id != OLD.workflow_id
        OR NEW.record_count <= OLD.record_count
        THEN RAISE(ABORT, 'durable-history head must advance monotonically') END;
END;
"""


def insert_durable_history_identity(
    connection: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    strategy_id: str,
    state_version: str,
    definition_hash: str,
) -> None:
    if not connection.in_transaction:
        raise PortabilityInvariantError(
            "durable-history identity requires an active creation transaction"
        )
    expected = _definition_values(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        strategy_id=strategy_id,
        state_version=state_version,
        definition_hash=definition_hash,
    )
    connection.execute(
        f"""
        INSERT INTO {DURABLE_DEFINITION_TABLE} (
            tenant_id, workflow_id, strategy_id, state_version, definition_hash
        ) VALUES (?, ?, ?, ?, ?)
        """,  # noqa: S608 -- table is a module constant
        expected,
    )
    connection.execute(
        f"""
        INSERT INTO {DURABLE_HEAD_TABLE} (
            tenant_id, workflow_id, record_count, record_head_hash
        ) VALUES (?, ?, 0, ?)
        """,  # noqa: S608 -- table is a module constant
        (tenant_id, workflow_id, "0" * 64),
    )


class SQLiteDurableHistoryStore:
    _connection: sqlite3.Connection
    _tenant_id: str
    _workflow_id: str
    _graph_revision: int

    def require_durable_history_definition(
        self,
        *,
        strategy_id: str,
        state_version: str,
        definition_hash: str,
    ) -> None:
        self._require_open()
        expected = _definition_values(
            tenant_id=self._tenant_id,
            workflow_id=self._workflow_id,
            strategy_id=strategy_id,
            state_version=state_version,
            definition_hash=definition_hash,
        )
        if self._durable_definition_row() != expected:
            raise PortabilityInvariantError(
                "SQLite durable-history definition pin is missing or changed"
            )

    def sync_durable_history(self, history: PortabilityHistory) -> None:
        self._require_open()
        if (
            history.tenant_id != self._tenant_id
            or history.workflow_id != self._workflow_id
            or history.graph_revision != self._graph_revision
        ):
            raise PortabilityInvariantError(
                "durable-history evidence scope or revision changed"
            )
        with self._write_transaction():
            existing = self._durable_history_records_unchecked()
            expected = durable_history_evidence(history)
            expected_set = set(expected)
            observed = {
                (record.record_type, record.command_id, record.evidence_hash)
                for record in existing
            }
            _verify_record_chain(existing)
            previous_hash = existing[-1].record_hash if existing else "0" * 64
            stored_head = self._durable_history_head_unchecked()
            if stored_head != DurableHistoryHead(len(existing), previous_hash):
                raise PortabilityInvariantError(
                    "SQLite durable-history chain does not match persisted head"
                )
            if len(observed) != len(existing) or not observed <= expected_set:
                raise PortabilityInvariantError(
                    "SQLite durable-history journal does not match evidence"
                )
            original_head = stored_head
            missing = tuple(
                identity for identity in expected if identity not in observed
            )
            _verify_missing_transaction_batch(existing, expected, missing)
            batch_sequence = existing[-1].batch_sequence + 1 if existing else 0
            for record_type, command_id, evidence_hash in missing:
                sequence = len(existing)
                record_hash = durable_history_record_hash(
                    sequence=sequence,
                    batch_sequence=batch_sequence,
                    record_type=record_type,
                    command_id=command_id,
                    evidence_hash=evidence_hash,
                    previous_record_hash=previous_hash,
                )
                try:
                    self._connection.execute(
                        f"""
                        INSERT INTO {DURABLE_RECORD_TABLE} (
                            tenant_id, workflow_id, sequence, batch_sequence, record_type,
                            command_id, evidence_hash, previous_record_hash,
                            record_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,  # noqa: S608 -- table is a module constant
                        (
                            self._tenant_id,
                            self._workflow_id,
                            sequence,
                            batch_sequence,
                            record_type,
                            command_id,
                            evidence_hash,
                            previous_hash,
                            record_hash,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise PortabilityConflictError(
                        f"SQLite durable-history evidence conflict: {exc}"
                    ) from exc
                record = DurableHistoryRecord(
                    sequence,
                    batch_sequence,
                    record_type,
                    command_id,
                    evidence_hash,
                    previous_hash,
                    record_hash,
                )
                existing = (*existing, record)
                observed.add((record_type, command_id, evidence_hash))
                previous_hash = record_hash
            final = {
                (record.record_type, record.command_id, record.evidence_hash)
                for record in existing
            }
            if final != expected_set:
                raise PortabilityInvariantError(
                    "SQLite durable-history journal is incomplete"
                )
            if len(existing) != original_head.record_count:
                cursor = self._connection.execute(
                    f"""
                    UPDATE {DURABLE_HEAD_TABLE}
                    SET record_count = ?, record_head_hash = ?
                    WHERE tenant_id = ? AND workflow_id = ?
                      AND record_count = ? AND record_head_hash = ?
                    """,  # noqa: S608 -- table is a module constant
                    (
                        len(existing),
                        previous_hash,
                        self._tenant_id,
                        self._workflow_id,
                        original_head.record_count,
                        original_head.record_head_hash,
                    ),
                )
                if cursor.rowcount != 1:
                    raise PortabilityConflictError(
                        "SQLite durable-history head changed concurrently"
                    )

    def durable_history_records(self) -> tuple[DurableHistoryRecord, ...]:
        self._require_open()
        return self._durable_history_records_unchecked()

    def durable_history_head(self) -> DurableHistoryHead:
        self._require_open()
        return self._durable_history_head_unchecked()

    def _durable_definition_row(self) -> tuple[object, ...] | None:
        row = self._connection.execute(
            f"""
            SELECT tenant_id, workflow_id, strategy_id, state_version,
                   definition_hash
            FROM {DURABLE_DEFINITION_TABLE}
            WHERE tenant_id = ? AND workflow_id = ?
            """,  # noqa: S608 -- table is a module constant
            (self._tenant_id, self._workflow_id),
        ).fetchone()
        return tuple(row) if row is not None else None

    def _durable_history_records_unchecked(self) -> tuple[DurableHistoryRecord, ...]:
        return tuple(
            DurableHistoryRecord(*row)
            for row in self._connection.execute(
                f"""
                SELECT sequence, batch_sequence, record_type, command_id, evidence_hash,
                       previous_record_hash, record_hash
                FROM {DURABLE_RECORD_TABLE}
                WHERE tenant_id = ? AND workflow_id = ?
                ORDER BY sequence
                """,  # noqa: S608 -- table is a module constant
                (self._tenant_id, self._workflow_id),
            )
        )

    def _durable_history_head_unchecked(self) -> DurableHistoryHead:
        row = self._connection.execute(
            f"""
            SELECT record_count, record_head_hash
            FROM {DURABLE_HEAD_TABLE}
            WHERE tenant_id = ? AND workflow_id = ?
            """,  # noqa: S608 -- table is a module constant
            (self._tenant_id, self._workflow_id),
        ).fetchone()
        if row is None:
            raise PortabilityInvariantError(
                "SQLite durable-history persisted head is missing"
            )
        return DurableHistoryHead(*row)


def _definition_values(
    *,
    tenant_id: str,
    workflow_id: str,
    strategy_id: str,
    state_version: str,
    definition_hash: str,
) -> tuple[object, ...]:
    if type(strategy_id) is not str or not strategy_id:
        raise PortabilityInvariantError("durable-history strategy_id must be non-empty")
    if type(state_version) is not str or not state_version:
        raise PortabilityInvariantError(
            "durable-history state version must be non-empty"
        )
    if (
        type(definition_hash) is not str
        or len(definition_hash) != 64
        or any(character not in "0123456789abcdef" for character in definition_hash)
    ):
        raise PortabilityInvariantError(
            "durable-history definition hash must be lowercase SHA-256"
        )
    return tenant_id, workflow_id, strategy_id, state_version, definition_hash


def _verify_record_chain(records: tuple[DurableHistoryRecord, ...]) -> None:
    previous_hash = "0" * 64
    for sequence, record in enumerate(records):
        expected_hash = durable_history_record_hash(
            sequence=sequence,
            batch_sequence=record.batch_sequence,
            record_type=record.record_type,
            command_id=record.command_id,
            evidence_hash=record.evidence_hash,
            previous_record_hash=previous_hash,
        )
        if (
            record.sequence != sequence
            or record.previous_record_hash != previous_hash
            or record.record_hash != expected_hash
        ):
            raise PortabilityInvariantError(
                "SQLite durable-history journal hash chain is invalid"
            )
        previous_hash = record.record_hash


def _verify_missing_transaction_batch(
    existing: tuple[DurableHistoryRecord, ...],
    expected: tuple[tuple[str, str, str], ...],
    missing: tuple[tuple[str, str, str], ...],
) -> None:
    if not missing:
        return
    command_ids = {command_id for _record_type, command_id, _digest in missing}
    if len(command_ids) != 1:
        raise PortabilityInvariantError(
            "durable-history recovery spans multiple source transactions"
        )
    command_id = next(iter(command_ids))
    expected_phases = [
        record_type
        for record_type, candidate_id, _digest in expected
        if candidate_id == command_id
    ]
    existing_phases = [
        record.record_type for record in existing if record.command_id == command_id
    ]
    missing_phases = [record_type for record_type, _command_id, _digest in missing]
    if [*existing_phases, *missing_phases] != expected_phases:
        raise PortabilityInvariantError(
            "durable-history recovery is not one causal transaction segment"
        )


__all__ = [
    "DURABLE_DEFINITION_TABLE",
    "DURABLE_HEAD_TABLE",
    "DURABLE_HISTORY_SCHEMA",
    "DURABLE_RECORD_TABLE",
    "SQLiteDurableHistoryStore",
    "insert_durable_history_identity",
]
