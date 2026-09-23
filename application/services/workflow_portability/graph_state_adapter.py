"""First-party graph-state strategy over portable SQLite evidence.

The graph projection is reconstructable optimization state. It never replaces
portable commands, events, receipts, checkpoints, or the independent effect
ledger as authority.
"""

from __future__ import annotations

from pathlib import Path

from application.ports.workflow_portability import (
    PortabilityClock,
    PortabilityEffectSink,
)
from application.services.workflow_portability.internal_kernel import (
    verify_portability_history,
)
from application.services.workflow_portability.sqlite_adapter import (
    SQLitePortabilityAdapter,
    SQLitePortabilityAdapterFactory,
)
from domain.workflow.graph_state import (
    GraphDefinition,
    GraphStateProjection,
    SEQUENTIAL_GRAPH_DEFINITION,
    project_graph_state,
    require_graph_operation_route,
    verify_graph_definition,
)
from domain.workflow.portability import (
    PortabilityCheckpoint,
    PortabilityCommand,
    PortabilityCommandReceipt,
    PortabilityFaultPoint,
    PortabilityGraphRevision,
    PortabilityHistory,
    PortabilityInvariantError,
    PortabilitySnapshot,
)


class GraphStatePortabilityAdapterFactory:
    """Factory for a graph strategy backed by isolated portable SQLite state."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        definition: GraphDefinition = SEQUENTIAL_GRAPH_DEFINITION,
    ) -> None:
        self.database_path = Path(database_path)
        self._definition = definition
        self._definition_hash = verify_graph_definition(definition)
        self._sqlite_factory = SQLitePortabilityAdapterFactory(self.database_path)

    def create(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        initial_topology: PortabilityGraphRevision | None = None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> GraphStatePortabilityAdapter:
        delegate = self._sqlite_factory.create(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            initial_topology=initial_topology,
            clock=clock,
            effect_sink=effect_sink,
        )
        try:
            delegate.bind_graph_definition(
                definition_id=self._definition.definition_id,
                state_version=self._definition.state_version,
                definition_hash=self._definition_hash,
            )
            return GraphStatePortabilityAdapter(
                delegate,
                definition=self._definition,
                definition_hash=self._definition_hash,
            )
        except Exception:
            delegate.close()
            raise

    def restore(
        self,
        *,
        history: PortabilityHistory,
        checkpoint: PortabilityCheckpoint,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> GraphStatePortabilityAdapter:
        delegate = self._sqlite_factory.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=effect_sink,
        )
        try:
            delegate.require_graph_definition(
                definition_id=self._definition.definition_id,
                state_version=self._definition.state_version,
                definition_hash=self._definition_hash,
            )
            return GraphStatePortabilityAdapter(
                delegate,
                definition=self._definition,
                definition_hash=self._definition_hash,
            )
        except Exception:
            delegate.close()
            raise


class GraphStatePortabilityAdapter:
    """Deterministic graph interpretation of authoritative portable history."""

    adapter_id = "graph-state-portability.v1"

    def __init__(
        self,
        delegate: SQLitePortabilityAdapter,
        *,
        definition: GraphDefinition,
        definition_hash: str,
    ) -> None:
        self._delegate = delegate
        self._definition = definition
        self._definition_hash = definition_hash
        self.graph_state()

    @property
    def database_path(self) -> Path:
        return self._delegate.database_path

    def close(self) -> None:
        self._delegate.close()

    def apply(
        self,
        command: PortabilityCommand,
        *,
        fault: PortabilityFaultPoint | None = None,
    ) -> PortabilityCommandReceipt:
        history = self._delegate.export_history()
        self._project(history)
        if not any(
            receipt.command_id == command.command_id
            for receipt in history.command_receipts
        ):
            require_graph_operation_route(
                history,
                verify_portability_history(history),
                command.operation,
                definition=self._definition,
                expected_definition_hash=self._definition_hash,
            )
        try:
            return self._delegate.apply(command, fault=fault)
        finally:
            # A fault after durable event commit still requires the graph view
            # to be reproducible from the evidence left behind.
            self.graph_state()

    def checkpoint(self) -> PortabilityCheckpoint:
        graph_before = self.graph_state()
        checkpoint = self._delegate.checkpoint()
        graph = self.graph_state()
        if (
            graph != graph_before
            or graph_before.event_sequence != checkpoint.event_sequence
            or graph_before.history_hash != checkpoint.history_hash
            or graph.event_sequence != checkpoint.event_sequence
            or graph.history_hash != checkpoint.history_hash
        ):
            raise PortabilityInvariantError(
                "graph cursor does not match portable checkpoint"
            )
        return checkpoint

    def snapshot(self) -> PortabilitySnapshot:
        snapshot = self._delegate.snapshot()
        graph = self.graph_state()
        if graph.workflow_status != snapshot.workflow_status:
            raise PortabilityInvariantError(
                "graph state does not match portable workflow snapshot"
            )
        return snapshot

    def export_history(self) -> PortabilityHistory:
        history = self._delegate.export_history()
        self._project(history)
        return history

    def graph_state(self) -> GraphStateProjection:
        return self._project(self._delegate.export_history())

    def evidence_counts(self) -> dict[str, int]:
        return self._delegate.evidence_counts()

    @property
    def connection_settings(self) -> dict[str, object]:
        return self._delegate.connection_settings

    def _project(self, history: PortabilityHistory) -> GraphStateProjection:
        self._delegate.require_graph_definition(
            definition_id=self._definition.definition_id,
            state_version=self._definition.state_version,
            definition_hash=self._definition_hash,
        )
        portable_snapshot = verify_portability_history(history)
        return project_graph_state(
            history,
            portable_snapshot,
            definition=self._definition,
            expected_definition_hash=self._definition_hash,
        )


__all__ = [
    "GraphStatePortabilityAdapter",
    "GraphStatePortabilityAdapterFactory",
]
