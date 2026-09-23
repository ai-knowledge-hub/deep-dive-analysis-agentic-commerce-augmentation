"""Application ports shared by workflow portability candidates and harnesses."""

from __future__ import annotations

from typing import Protocol

from domain.workflow.portability import (
    PortabilityCheckpoint,
    PortabilityCommand,
    PortabilityCommandReceipt,
    PortabilityEffectExecution,
    PortabilityEffectReceipt,
    PortabilityFaultPoint,
    PortabilityGraphRevision,
    PortabilityHistory,
    PortabilitySnapshot,
)


class PortabilityClock(Protocol):
    @property
    def now_tick(self) -> int: ...


class PortabilityEffectSink(Protocol):
    def execute(self, command: PortabilityCommand) -> str: ...

    def execution_for(
        self, *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> PortabilityEffectExecution | None: ...

    def receipt_for(
        self, *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> PortabilityEffectReceipt | None: ...

    def persist_receipt(self, receipt: PortabilityEffectReceipt) -> None: ...

    def export_receipts(
        self, *, tenant_id: str, workflow_id: str
    ) -> tuple[PortabilityEffectReceipt, ...]: ...

    def export_executions(
        self, *, tenant_id: str, workflow_id: str
    ) -> tuple[PortabilityEffectExecution, ...]: ...


class WorkflowFrameworkAdapter(Protocol):
    @property
    def adapter_id(self) -> str: ...

    def apply(
        self,
        command: PortabilityCommand,
        *,
        fault: PortabilityFaultPoint | None = None,
    ) -> PortabilityCommandReceipt: ...

    def checkpoint(self) -> PortabilityCheckpoint: ...

    def snapshot(self) -> PortabilitySnapshot: ...

    def export_history(self) -> PortabilityHistory: ...


class WorkflowFrameworkAdapterFactory(Protocol):
    def create(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int,
        initial_topology: PortabilityGraphRevision | None = None,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> WorkflowFrameworkAdapter: ...

    def restore(
        self,
        *,
        history: PortabilityHistory,
        checkpoint: PortabilityCheckpoint,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> WorkflowFrameworkAdapter: ...


__all__ = [
    "PortabilityClock",
    "PortabilityEffectSink",
    "WorkflowFrameworkAdapter",
    "WorkflowFrameworkAdapterFactory",
]
