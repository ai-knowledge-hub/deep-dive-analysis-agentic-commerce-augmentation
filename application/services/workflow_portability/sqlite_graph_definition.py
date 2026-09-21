"""Immutable graph-definition evidence for the SQLite portability store."""

from __future__ import annotations

import sqlite3

from domain.workflow.portability import (
    PortabilityConflictError,
    PortabilityInvariantError,
)


GRAPH_DEFINITION_TABLE = "portability_benchmark_graph_definitions"
GRAPH_DEFINITION_SCHEMA = f"""
CREATE TABLE {GRAPH_DEFINITION_TABLE} (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    definition_id TEXT NOT NULL CHECK (length(definition_id) > 0),
    state_version TEXT NOT NULL CHECK (length(state_version) > 0),
    definition_hash TEXT NOT NULL CHECK (length(definition_hash) = 64),
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES portability_benchmark_workflows (tenant_id, workflow_id)
);
"""


class SQLiteGraphDefinitionStore:
    """Mixin that binds an exact graph definition to one workflow identity."""

    _connection: sqlite3.Connection
    _tenant_id: str
    _workflow_id: str

    def bind_graph_definition(
        self,
        *,
        definition_id: str,
        state_version: str,
        definition_hash: str,
    ) -> None:
        expected = _definition_values(
            tenant_id=self._tenant_id,
            workflow_id=self._workflow_id,
            definition_id=definition_id,
            state_version=state_version,
            definition_hash=definition_hash,
        )
        with self._write_transaction():
            self._connection.execute(
                f"""
                INSERT INTO {GRAPH_DEFINITION_TABLE} (
                    tenant_id, workflow_id, definition_id, state_version,
                    definition_hash
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, workflow_id) DO NOTHING
                """,  # noqa: S608 -- the table is a module constant
                expected,
            )
            if self._graph_definition_row() != expected:
                raise PortabilityConflictError(
                    "SQLite graph definition identity changed"
                )

    def require_graph_definition(
        self,
        *,
        definition_id: str,
        state_version: str,
        definition_hash: str,
    ) -> None:
        self._require_open()
        expected = _definition_values(
            tenant_id=self._tenant_id,
            workflow_id=self._workflow_id,
            definition_id=definition_id,
            state_version=state_version,
            definition_hash=definition_hash,
        )
        if self._graph_definition_row() != expected:
            raise PortabilityInvariantError(
                "SQLite graph definition pin is missing or changed"
            )

    def _graph_definition_row(self) -> tuple[object, ...] | None:
        row = self._connection.execute(
            f"""
            SELECT tenant_id, workflow_id, definition_id, state_version,
                   definition_hash
            FROM {GRAPH_DEFINITION_TABLE}
            WHERE tenant_id = ? AND workflow_id = ?
            """,  # noqa: S608 -- the table is a module constant
            (self._tenant_id, self._workflow_id),
        ).fetchone()
        return tuple(row) if row is not None else None


def _definition_values(
    *,
    tenant_id: str,
    workflow_id: str,
    definition_id: str,
    state_version: str,
    definition_hash: str,
) -> tuple[object, ...]:
    if type(definition_id) is not str or not definition_id:
        raise PortabilityInvariantError("graph definition_id must be non-empty")
    if type(state_version) is not str or not state_version:
        raise PortabilityInvariantError("graph state version must be non-empty")
    if (
        type(definition_hash) is not str
        or len(definition_hash) != 64
        or any(character not in "0123456789abcdef" for character in definition_hash)
    ):
        raise PortabilityInvariantError(
            "graph definition hash must be lowercase SHA-256"
        )
    return (
        tenant_id,
        workflow_id,
        definition_id,
        state_version,
        definition_hash,
    )


__all__ = [
    "GRAPH_DEFINITION_SCHEMA",
    "GRAPH_DEFINITION_TABLE",
    "SQLiteGraphDefinitionStore",
]
