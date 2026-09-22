"""First-party durable-history orchestration over portable SQLite evidence.

The journal records recoverable orchestration decisions and commit boundaries.
Portable commands, events, receipts, checkpoints, and the independent effect
ledger remain authoritative.
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
from domain.workflow.durable_history import (
    DURABLE_HISTORY_DEFINITION,
    DurableHistoryDefinition,
    DurableHistoryProjection,
    project_durable_history,
    verify_durable_history_definition,
)
from domain.workflow.portability import (
    PortabilityCheckpoint,
    PortabilityCommand,
    PortabilityCommandReceipt,
    PortabilityFaultPoint,
    PortabilityHistory,
    PortabilityInvariantError,
    PortabilitySnapshot,
)


class DurableHistoryPortabilityAdapterFactory:
    """Factory for the platform-owned durable-history strategy."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        definition: DurableHistoryDefinition = DURABLE_HISTORY_DEFINITION,
    ) -> None:
        self.database_path = Path(database_path)
        self._definition = definition
        self._definition_hash = verify_durable_history_definition(definition)
        self._sqlite_factory = SQLitePortabilityAdapterFactory(self.database_path)

    def create(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> DurableHistoryPortabilityAdapter:
        delegate = self._sqlite_factory.create_with_durable_history(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            clock=clock,
            effect_sink=effect_sink,
            strategy_id=self._definition.strategy_id,
            state_version=self._definition.state_version,
            definition_hash=self._definition_hash,
        )
        try:
            return DurableHistoryPortabilityAdapter(
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
    ) -> DurableHistoryPortabilityAdapter:
        delegate = self._sqlite_factory.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=effect_sink,
        )
        try:
            delegate.require_durable_history_definition(
                strategy_id=self._definition.strategy_id,
                state_version=self._definition.state_version,
                definition_hash=self._definition_hash,
            )
            return DurableHistoryPortabilityAdapter(
                delegate,
                definition=self._definition,
                definition_hash=self._definition_hash,
            )
        except Exception:
            delegate.close()
            raise


class DurableHistoryPortabilityAdapter:
    """Durable decision journal reconstructed from authoritative evidence."""

    adapter_id = "durable-history-portability.v1"

    def __init__(
        self,
        delegate: SQLitePortabilityAdapter,
        *,
        definition: DurableHistoryDefinition,
        definition_hash: str,
    ) -> None:
        self._delegate = delegate
        self._definition = definition
        self._definition_hash = definition_hash
        self.durable_history_state()

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
        self.durable_history_state()
        try:
            receipt = self._delegate.apply(command, fault=fault)
        except Exception:
            self.durable_history_state()
            raise
        self.durable_history_state()
        return receipt

    def checkpoint(self) -> PortabilityCheckpoint:
        state_before = self.durable_history_state()
        checkpoint = self._delegate.checkpoint()
        state = self.durable_history_state()
        if (
            state != state_before
            or state.event_sequence != checkpoint.event_sequence
            or state.history_hash != checkpoint.history_hash
        ):
            raise PortabilityInvariantError(
                "durable-history cursor does not match portable checkpoint"
            )
        return checkpoint

    def snapshot(self) -> PortabilitySnapshot:
        snapshot = self._delegate.snapshot()
        state = self.durable_history_state()
        if state.workflow_status != snapshot.workflow_status:
            raise PortabilityInvariantError(
                "durable-history state does not match portable snapshot"
            )
        return snapshot

    def export_history(self) -> PortabilityHistory:
        history = self._delegate.export_history()
        self._project(history)
        return history

    def durable_history_state(self) -> DurableHistoryProjection:
        return self._project(self._delegate.export_history())

    def evidence_counts(self) -> dict[str, int]:
        return self._delegate.evidence_counts()

    @property
    def connection_settings(self) -> dict[str, object]:
        return self._delegate.connection_settings

    def _project(self, history: PortabilityHistory) -> DurableHistoryProjection:
        self._delegate.require_durable_history_definition(
            strategy_id=self._definition.strategy_id,
            state_version=self._definition.state_version,
            definition_hash=self._definition_hash,
        )
        portable_snapshot = verify_portability_history(history)
        self._delegate.sync_durable_history(history)
        return project_durable_history(
            history,
            portable_snapshot,
            self._delegate.durable_history_records(),
            self._delegate.durable_history_head(),
            definition=self._definition,
            expected_definition_hash=self._definition_hash,
        )


__all__ = [
    "DurableHistoryPortabilityAdapter",
    "DurableHistoryPortabilityAdapterFactory",
]
