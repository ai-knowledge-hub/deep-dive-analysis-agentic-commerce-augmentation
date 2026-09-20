"""Independent deterministic clock and effect oracle for portability tests."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from domain.workflow.portability import (
    PortabilityCommand,
    PortabilityConflictError,
    PortabilityEffectExecution,
    PortabilityEffectReceipt,
    PortabilityInvariantError,
    PortabilityOperation,
    portability_command_digest,
)


@dataclass
class DeterministicClock:
    now_tick: int = 0

    def advance(self, ticks: int) -> None:
        if type(ticks) is not int or ticks < 1:
            raise PortabilityInvariantError("clock advance must be positive")
        self.now_tick += ticks


@dataclass
class DeterministicEffectSink:
    """Harness-owned provider and immutable receipt ledger.

    Provider execution is idempotent by tenant/workflow/effect identity. Calls
    and actual executions are tracked separately so an adapter cannot certify
    at-most-once effects merely by exporting one event.
    """

    _executions: dict[tuple[str, str, str], PortabilityEffectExecution] = field(
        default_factory=dict
    )
    _execution_calls: dict[tuple[str, str, str], int] = field(default_factory=dict)
    _receipts: dict[tuple[str, str, str], PortabilityEffectReceipt] = field(
        default_factory=dict
    )

    def execute(self, command: PortabilityCommand) -> str:
        if command.operation is not PortabilityOperation.COMMIT_EFFECT:
            raise PortabilityInvariantError("effect sink accepts only effect commands")
        key = self._key(
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            effect_id=command.effect_id or "",
        )
        request_hash = portability_command_digest(command)
        provider_receipt_id = hashlib.sha256(
            "\x00".join((*key, request_hash)).encode("utf-8")
        ).hexdigest()
        candidate = PortabilityEffectExecution(
            command=command,
            request_hash=request_hash,
            provider_receipt_id=provider_receipt_id,
        )
        existing = self._executions.get(key)
        if existing is not None and existing != candidate:
            raise PortabilityConflictError(
                "effect identity reused with changed execution provenance"
            )
        self._execution_calls[key] = self._execution_calls.get(key, 0) + 1
        self._executions.setdefault(key, candidate)
        return provider_receipt_id

    def receipt_for(
        self, *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> PortabilityEffectReceipt | None:
        return self._receipts.get(
            self._key(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                effect_id=effect_id,
            )
        )

    def execution_for(
        self, *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> PortabilityEffectExecution | None:
        return self._executions.get(
            self._key(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                effect_id=effect_id,
            )
        )

    def persist_receipt(self, receipt: PortabilityEffectReceipt) -> None:
        key = self._key(
            tenant_id=receipt.tenant_id,
            workflow_id=receipt.workflow_id,
            effect_id=receipt.effect_id,
        )
        executed = self._executions.get(key)
        if executed is None:
            raise PortabilityInvariantError("cannot receipt an unexecuted effect")
        command = executed.command
        if (
            executed.request_hash != receipt.request_hash
            or executed.provider_receipt_id != receipt.provider_receipt_id
            or command.effect_id != receipt.effect_id
            or command.command_id != receipt.command_id
            or command.tenant_id != receipt.tenant_id
            or command.workflow_id != receipt.workflow_id
            or command.graph_revision != receipt.graph_revision
            or command.task_id != receipt.task_id
            or command.attempt_id != receipt.attempt_id
            or command.worker_id != receipt.worker_id
            or command.fencing_token != receipt.fencing_token
            or command.payload_hash != receipt.payload_hash
        ):
            raise PortabilityConflictError("effect receipt does not match provider")
        existing = self._receipts.get(key)
        if existing is not None and existing != receipt:
            raise PortabilityConflictError("effect receipt is immutable")
        self._receipts.setdefault(key, receipt)

    def export_receipts(
        self, *, tenant_id: str, workflow_id: str
    ) -> tuple[PortabilityEffectReceipt, ...]:
        return tuple(
            sorted(
                (
                    receipt
                    for (
                        scope_tenant,
                        scope_workflow,
                        _,
                    ), receipt in self._receipts.items()
                    if scope_tenant == tenant_id and scope_workflow == workflow_id
                ),
                key=lambda receipt: receipt.effect_id,
            )
        )

    def export_executions(
        self, *, tenant_id: str, workflow_id: str
    ) -> tuple[PortabilityEffectExecution, ...]:
        return tuple(
            sorted(
                (
                    execution
                    for (
                        scope_tenant,
                        scope_workflow,
                        _,
                    ), execution in self._executions.items()
                    if scope_tenant == tenant_id and scope_workflow == workflow_id
                ),
                key=lambda execution: (
                    execution.command.effect_id or "",
                    execution.command.command_id,
                ),
            )
        )

    def actual_effect_count(
        self, *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> int:
        key = self._key(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            effect_id=effect_id,
        )
        return int(key in self._executions)

    def execution_call_count(
        self, *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> int:
        return self._execution_calls.get(
            self._key(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                effect_id=effect_id,
            ),
            0,
        )

    @staticmethod
    def _key(
        *, tenant_id: str, workflow_id: str, effect_id: str
    ) -> tuple[str, str, str]:
        return tenant_id, workflow_id, effect_id


__all__ = ["DeterministicClock", "DeterministicEffectSink"]
