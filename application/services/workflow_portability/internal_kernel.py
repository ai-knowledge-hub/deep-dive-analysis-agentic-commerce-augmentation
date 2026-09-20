"""Deterministic internal-kernel baseline for framework comparison.

This is benchmark code, not a production scheduler. The adapter owns workflow
events while the harness independently owns time, actual effects, and provider
receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json

from application.ports.workflow_portability import (
    PortabilityClock,
    PortabilityEffectSink,
)
from domain.workflow.lifecycle import WorkflowStatus, require_workflow_transition
from domain.workflow.portability import (
    PORTABILITY_CONTRACT_VERSION,
    PortabilityCheckpoint,
    PortabilityCommand,
    PortabilityCommandReceipt,
    PortabilityConflictError,
    PortabilityEffectReceipt,
    PortabilityEvent,
    PortabilityFaultPoint,
    PortabilityHistory,
    PortabilityInjectedCrash,
    PortabilityInvariantError,
    PortabilityOperation,
    PortabilitySnapshot,
    canonical_event_payload,
    portability_command_digest,
    portability_history_digest,
)


AttemptState = tuple[str, str, int, int]


@dataclass
class InternalKernelStore:
    tenant_id: str
    workflow_id: str
    graph_revision: int
    commands: dict[str, PortabilityCommand] = field(default_factory=dict)
    events: list[PortabilityEvent] = field(default_factory=list)
    command_receipts: dict[str, PortabilityCommandReceipt] = field(default_factory=dict)


class InternalKernelAdapter:
    adapter_id = "internal-kernel.v2"

    def __init__(
        self,
        store: InternalKernelStore,
        *,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> None:
        self._store = store
        self._clock = clock
        self._effect_sink = effect_sink
        history = self.export_history()
        verify_portability_history(history)
        _verify_effect_sink_bindings(history, effect_sink)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        workflow_id: str,
        graph_revision: int = 1,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> InternalKernelAdapter:
        if type(tenant_id) is not str or not tenant_id:
            raise PortabilityInvariantError("tenant_id must be a non-empty string")
        if type(workflow_id) is not str or not workflow_id:
            raise PortabilityInvariantError("workflow_id must be a non-empty string")
        if type(graph_revision) is not int or graph_revision < 1:
            raise PortabilityInvariantError("graph_revision must be a positive integer")
        return cls(
            InternalKernelStore(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                graph_revision=graph_revision,
            ),
            clock=clock,
            effect_sink=effect_sink,
        )

    @classmethod
    def restore(
        cls,
        *,
        history: PortabilityHistory,
        checkpoint: PortabilityCheckpoint,
        clock: PortabilityClock,
        effect_sink: PortabilityEffectSink,
    ) -> InternalKernelAdapter:
        snapshot = verify_portability_history(history)
        _verify_checkpoint(checkpoint, history, snapshot)
        _verify_effect_sink_bindings(history, effect_sink)
        store = InternalKernelStore(
            tenant_id=history.tenant_id,
            workflow_id=history.workflow_id,
            graph_revision=history.graph_revision,
            commands={command.command_id: command for command in history.commands},
            events=list(history.events),
            command_receipts={
                receipt.command_id: receipt for receipt in history.command_receipts
            },
        )
        return cls(store, clock=clock, effect_sink=effect_sink)

    def apply(
        self,
        command: PortabilityCommand,
        *,
        fault: PortabilityFaultPoint | None = None,
    ) -> PortabilityCommandReceipt:
        self._require_fault(command, fault)
        self._require_scope(command)
        request_hash = portability_command_digest(command)
        recorded_command = self._store.commands.get(command.command_id)
        if recorded_command is not None and recorded_command != command:
            raise PortabilityConflictError(
                "command identity reused with changed payload"
            )
        existing_receipt = self._store.command_receipts.get(command.command_id)
        if existing_receipt is not None:
            if existing_receipt.request_hash != request_hash:
                raise PortabilityConflictError(
                    "command identity reused with changed request hash"
                )
            return existing_receipt

        provider_receipt_id: str | None = None
        if command.operation is PortabilityOperation.COMMIT_EFFECT:
            for recorded in self._store.commands.values():
                if (
                    recorded.operation is PortabilityOperation.COMMIT_EFFECT
                    and recorded.effect_id == command.effect_id
                    and recorded.command_id != command.command_id
                ):
                    raise PortabilityConflictError(
                        "effect identity is already bound to another command"
                    )
            execution = self._effect_sink.execution_for(
                tenant_id=command.tenant_id,
                workflow_id=command.workflow_id,
                effect_id=command.effect_id or "",
            )
            if execution is not None:
                if (
                    execution.command != command
                    or execution.request_hash != request_hash
                ):
                    raise PortabilityConflictError(
                        "provider execution is bound to different provenance"
                    )
                provider_receipt_id = execution.provider_receipt_id
            recorded_effect_receipt = self._effect_sink.receipt_for(
                tenant_id=command.tenant_id,
                workflow_id=command.workflow_id,
                effect_id=command.effect_id or "",
            )
            if provider_receipt_id is not None and recorded_effect_receipt is not None:
                candidate = _effect_receipt(
                    command=command,
                    request_hash=request_hash,
                    provider_receipt_id=provider_receipt_id,
                )
                if recorded_effect_receipt != candidate:
                    raise PortabilityConflictError("effect receipt binding changed")
        reconciling_executed_effect = provider_receipt_id is not None
        if not reconciling_executed_effect:
            self._validate_command(command)
        self._store.commands.setdefault(command.command_id, command)

        if command.operation is PortabilityOperation.COMMIT_EFFECT:
            if provider_receipt_id is None:
                self._crash(fault, PortabilityFaultPoint.BEFORE_EFFECT, executed=False)
                provider_receipt_id = self._effect_sink.execute(command)
                execution = self._effect_sink.execution_for(
                    tenant_id=command.tenant_id,
                    workflow_id=command.workflow_id,
                    effect_id=command.effect_id or "",
                )
                if (
                    execution is None
                    or execution.command != command
                    or execution.request_hash != request_hash
                    or execution.provider_receipt_id != provider_receipt_id
                ):
                    raise PortabilityInvariantError(
                        "effect sink returned mismatched execution evidence"
                    )
                self._crash(
                    fault,
                    PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
                    executed=True,
                )
            effect_receipt = _effect_receipt(
                command=command,
                request_hash=request_hash,
                provider_receipt_id=provider_receipt_id,
            )
            existing_effect_receipt = self._effect_sink.receipt_for(
                tenant_id=command.tenant_id,
                workflow_id=command.workflow_id,
                effect_id=command.effect_id or "",
            )
            if (
                existing_effect_receipt is not None
                and existing_effect_receipt != effect_receipt
            ):
                raise PortabilityConflictError("effect receipt binding changed")
            self._effect_sink.persist_receipt(effect_receipt)
            self._crash(
                fault,
                PortabilityFaultPoint.AFTER_RECEIPT_BEFORE_EVENT_COMMIT,
                executed=True,
            )
        self._crash(
            fault,
            PortabilityFaultPoint.BEFORE_EVENT_COMMIT,
            executed=provider_receipt_id is not None,
        )

        event = self._event_for_command(
            command,
            provider_receipt_id=provider_receipt_id,
            reconciled=reconciling_executed_effect,
        )
        receipt = PortabilityCommandReceipt(
            command_id=command.command_id,
            request_hash=request_hash,
            first_event_sequence=event.sequence,
            last_event_sequence=event.sequence,
        )
        prospective_events = (*self._store.events, event)
        prospective_receipts = {
            **self._store.command_receipts,
            command.command_id: receipt,
        }
        verify_portability_history(
            self._history(
                events=prospective_events,
                command_receipts=prospective_receipts,
            )
        )
        self._store.events.append(event)
        self._store.command_receipts[command.command_id] = receipt
        self._crash(
            fault,
            PortabilityFaultPoint.AFTER_EVENT_COMMIT_BEFORE_ACK,
            executed=provider_receipt_id is not None,
        )
        return receipt

    def checkpoint(self) -> PortabilityCheckpoint:
        history = self.export_history()
        return PortabilityCheckpoint(
            contract_version=history.contract_version,
            tenant_id=history.tenant_id,
            workflow_id=history.workflow_id,
            graph_revision=history.graph_revision,
            event_sequence=len(history.events) - 1,
            history_hash=history.history_hash,
            committed_receipt_ids=tuple(
                receipt.provider_receipt_id for receipt in history.effect_receipts
            ),
            snapshot=self.snapshot(),
        )

    def snapshot(self) -> PortabilitySnapshot:
        return _replay(
            tenant_id=self._store.tenant_id,
            workflow_id=self._store.workflow_id,
            graph_revision=self._store.graph_revision,
            commands=tuple(self._store.commands.values()),
            events=tuple(self._store.events),
            effect_receipts=self._effect_sink.export_receipts(
                tenant_id=self._store.tenant_id,
                workflow_id=self._store.workflow_id,
            ),
        )

    def export_history(self) -> PortabilityHistory:
        return self._history(
            events=tuple(self._store.events),
            command_receipts=self._store.command_receipts,
        )

    def _history(
        self,
        *,
        events: tuple[PortabilityEvent, ...],
        command_receipts: dict[str, PortabilityCommandReceipt],
    ) -> PortabilityHistory:
        commands = tuple(
            self._store.commands[key] for key in sorted(self._store.commands)
        )
        receipts = tuple(command_receipts[key] for key in sorted(command_receipts))
        effect_receipts = self._effect_sink.export_receipts(
            tenant_id=self._store.tenant_id,
            workflow_id=self._store.workflow_id,
        )
        return _history(
            tenant_id=self._store.tenant_id,
            workflow_id=self._store.workflow_id,
            graph_revision=self._store.graph_revision,
            commands=commands,
            events=events,
            command_receipts=receipts,
            effect_receipts=effect_receipts,
        )

    def _require_scope(self, command: PortabilityCommand) -> None:
        if (
            command.tenant_id != self._store.tenant_id
            or command.workflow_id != self._store.workflow_id
            or command.graph_revision != self._store.graph_revision
        ):
            raise PortabilityInvariantError(
                "command scope or graph revision does not match workflow"
            )

    @staticmethod
    def _require_fault(
        command: PortabilityCommand, fault: PortabilityFaultPoint | None
    ) -> None:
        if fault is not None and type(fault) is not PortabilityFaultPoint:
            raise PortabilityInvariantError("fault must be a PortabilityFaultPoint")
        effect_only = {
            PortabilityFaultPoint.BEFORE_EFFECT,
            PortabilityFaultPoint.AFTER_EFFECT_BEFORE_RECEIPT,
            PortabilityFaultPoint.AFTER_RECEIPT_BEFORE_EVENT_COMMIT,
        }
        if (
            fault in effect_only
            and command.operation is not PortabilityOperation.COMMIT_EFFECT
        ):
            raise PortabilityInvariantError("effect fault requires an effect command")

    @staticmethod
    def _crash(
        selected: PortabilityFaultPoint | None,
        point: PortabilityFaultPoint,
        *,
        executed: bool,
    ) -> None:
        if selected is point:
            raise PortabilityInjectedCrash(point, effect_executed=executed)

    def _validate_command(self, command: PortabilityCommand) -> None:
        snapshot = self.snapshot()
        if command.operation is PortabilityOperation.START_WORKFLOW:
            _require_status_transition(snapshot, WorkflowStatus.RUNNING)
        elif command.operation is PortabilityOperation.PAUSE_WORKFLOW:
            _require_status_transition(snapshot, WorkflowStatus.PAUSED)
        elif command.operation is PortabilityOperation.RESUME_WORKFLOW:
            _require_status_transition(snapshot, WorkflowStatus.RUNNING)
        elif command.operation is PortabilityOperation.ASSIGN_ATTEMPT:
            _require_running(snapshot)
            current = _active_attempts(snapshot).get(command.task_id or "")
            if current is not None:
                if self._clock.now_tick < current[3]:
                    raise PortabilityInvariantError("cannot replace an unexpired lease")
                if int(command.fencing_token or 0) <= current[2]:
                    raise PortabilityInvariantError(
                        "attempt fencing token must increase"
                    )
            if int(command.lease_expires_at_tick or 0) <= self._clock.now_tick:
                raise PortabilityInvariantError("new attempt lease must be unexpired")
        elif command.operation is PortabilityOperation.HEARTBEAT_ATTEMPT:
            _require_running(snapshot)
            current = _active_attempts(snapshot).get(command.task_id or "")
            expected = (
                command.attempt_id,
                command.worker_id,
                command.fencing_token,
            )
            if current is None or current[:3] != expected:
                raise PortabilityInvariantError("stale worker cannot heartbeat lease")
            if self._clock.now_tick >= current[3]:
                raise PortabilityInvariantError("expired lease cannot be revived")
            if int(command.lease_expires_at_tick or 0) <= current[3]:
                raise PortabilityInvariantError("heartbeat must extend the lease")
        elif command.operation is PortabilityOperation.COMMIT_EFFECT:
            _require_running(snapshot)
            current = _active_attempts(snapshot).get(command.task_id or "")
            expected = (
                command.attempt_id,
                command.worker_id,
                command.fencing_token,
            )
            if current is None or current[:3] != expected:
                raise PortabilityInvariantError("stale attempt cannot commit an effect")
            if self._clock.now_tick >= current[3]:
                raise PortabilityInvariantError("expired lease cannot commit an effect")
            if command.effect_id in dict(
                (effect_id, payload_hash)
                for effect_id, payload_hash, _ in snapshot.committed_effects
            ):
                raise PortabilityConflictError("effect identity is already committed")
        elif command.operation is PortabilityOperation.COMPLETE_WORKFLOW:
            _require_status_transition(snapshot, WorkflowStatus.COMPLETED)
        else:
            _require_status_transition(snapshot, WorkflowStatus.CANCELED)

    def _event_for_command(
        self,
        command: PortabilityCommand,
        *,
        provider_receipt_id: str | None,
        reconciled: bool,
    ) -> PortabilityEvent:
        event_type = {
            PortabilityOperation.START_WORKFLOW: "workflow_started",
            PortabilityOperation.PAUSE_WORKFLOW: "workflow_paused",
            PortabilityOperation.RESUME_WORKFLOW: "workflow_resumed",
            PortabilityOperation.ASSIGN_ATTEMPT: "attempt_assigned",
            PortabilityOperation.HEARTBEAT_ATTEMPT: "attempt_heartbeat",
            PortabilityOperation.COMMIT_EFFECT: (
                "effect_reconciled" if reconciled else "effect_committed"
            ),
            PortabilityOperation.COMPLETE_WORKFLOW: "workflow_completed",
            PortabilityOperation.CANCEL_WORKFLOW: "workflow_canceled",
        }[command.operation]
        payload: dict[str, object] = {}
        if command.operation in {
            PortabilityOperation.ASSIGN_ATTEMPT,
            PortabilityOperation.HEARTBEAT_ATTEMPT,
        }:
            payload = {
                "attempt_id": command.attempt_id,
                "fencing_token": command.fencing_token,
                "lease_expires_at_tick": command.lease_expires_at_tick,
                "task_id": command.task_id,
                "worker_id": command.worker_id,
            }
        elif command.operation is PortabilityOperation.COMMIT_EFFECT:
            payload = {
                "attempt_id": command.attempt_id,
                "effect_id": command.effect_id,
                "fencing_token": command.fencing_token,
                "payload_hash": command.payload_hash,
                "provider_receipt_id": provider_receipt_id,
                "task_id": command.task_id,
                "worker_id": command.worker_id,
            }
        return PortabilityEvent(
            sequence=len(self._store.events),
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            event_type=event_type,
            command_id=command.command_id,
            payload_json=canonical_event_payload(payload),
        )


def verify_portability_history(history: PortabilityHistory) -> PortabilitySnapshot:
    _validate_history_header(history)
    expected_hash = portability_history_digest(
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
        graph_revision=history.graph_revision,
        commands=history.commands,
        events=history.events,
        command_receipts=history.command_receipts,
        effect_receipts=history.effect_receipts,
    )
    if history.history_hash != expected_hash:
        raise PortabilityInvariantError("portability history digest mismatch")
    if history.commands != tuple(
        sorted(history.commands, key=lambda command: command.command_id)
    ):
        raise PortabilityInvariantError("commands must be canonically ordered")
    if history.command_receipts != tuple(
        sorted(history.command_receipts, key=lambda receipt: receipt.command_id)
    ):
        raise PortabilityInvariantError("command receipts must be canonically ordered")
    if history.effect_receipts != tuple(
        sorted(history.effect_receipts, key=lambda receipt: receipt.effect_id)
    ):
        raise PortabilityInvariantError("effect receipts must be canonically ordered")

    commands: dict[str, PortabilityCommand] = {}
    for command in history.commands:
        if (
            command.tenant_id != history.tenant_id
            or command.workflow_id != history.workflow_id
            or command.graph_revision != history.graph_revision
        ):
            raise PortabilityInvariantError("command scope does not match history")
        if command.command_id in commands:
            raise PortabilityInvariantError("duplicate command evidence")
        commands[command.command_id] = command

    receipts: dict[str, PortabilityCommandReceipt] = {}
    for receipt in history.command_receipts:
        command = commands.get(receipt.command_id)
        if command is None:
            raise PortabilityInvariantError("command receipt lacks command evidence")
        if receipt.command_id in receipts:
            raise PortabilityInvariantError("duplicate command receipt")
        if receipt.request_hash != portability_command_digest(command):
            raise PortabilityInvariantError("command receipt request hash mismatch")
        if (
            type(receipt.first_event_sequence) is not int
            or type(receipt.last_event_sequence) is not int
            or receipt.first_event_sequence != receipt.last_event_sequence
            or not 0 <= receipt.first_event_sequence < len(history.events)
        ):
            raise PortabilityInvariantError("command receipt event range is invalid")
        event = history.events[receipt.first_event_sequence]
        if event.command_id != receipt.command_id:
            raise PortabilityInvariantError("command receipt does not bind its event")
        receipts[receipt.command_id] = receipt

    event_command_ids = [event.command_id for event in history.events]
    if len(event_command_ids) != len(set(event_command_ids)):
        raise PortabilityInvariantError("event command identity is duplicated")
    if set(event_command_ids) != set(receipts):
        raise PortabilityInvariantError("events and command receipts must be complete")

    effect_receipts: dict[str, PortabilityEffectReceipt] = {}
    for receipt in history.effect_receipts:
        command = commands.get(receipt.command_id)
        if (
            command is None
            or command.operation is not PortabilityOperation.COMMIT_EFFECT
        ):
            raise PortabilityInvariantError(
                "effect receipt lacks effect command evidence"
            )
        if receipt.effect_id in effect_receipts:
            raise PortabilityInvariantError("duplicate effect receipt")
        if receipt != _effect_receipt(
            command=command,
            request_hash=portability_command_digest(command),
            provider_receipt_id=receipt.provider_receipt_id,
        ):
            raise PortabilityInvariantError("effect receipt binding mismatch")
        effect_receipts[receipt.effect_id] = receipt

    return _replay(
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
        graph_revision=history.graph_revision,
        commands=history.commands,
        events=history.events,
        effect_receipts=history.effect_receipts,
    )


def _replay(
    *,
    tenant_id: str,
    workflow_id: str,
    graph_revision: int,
    commands: tuple[PortabilityCommand, ...],
    events: tuple[PortabilityEvent, ...],
    effect_receipts: tuple[PortabilityEffectReceipt, ...],
) -> PortabilitySnapshot:
    status = WorkflowStatus.PLANNED
    attempts: dict[str, AttemptState] = {}
    effects: dict[str, tuple[str, str]] = {}
    command_map = {command.command_id: command for command in commands}
    effect_receipt_map = {receipt.effect_id: receipt for receipt in effect_receipts}
    for expected_sequence, event in enumerate(events):
        if type(event.sequence) is not int or event.sequence != expected_sequence:
            raise PortabilityInvariantError("event history must be gap-free")
        if event.tenant_id != tenant_id or event.workflow_id != workflow_id:
            raise PortabilityInvariantError("event scope does not match history")
        command = command_map.get(event.command_id)
        if command is None:
            raise PortabilityInvariantError("event lacks command evidence")
        payload = _event_payload(event)
        expected_types = _expected_event_types(command.operation)
        if event.event_type not in expected_types:
            raise PortabilityInvariantError("event type does not match command")

        if event.event_type == "workflow_started":
            _require_payload_keys(payload, frozenset())
            _replay_transition(status, WorkflowStatus.RUNNING)
            status = WorkflowStatus.RUNNING
        elif event.event_type == "workflow_paused":
            _require_payload_keys(payload, frozenset())
            _replay_transition(status, WorkflowStatus.PAUSED)
            status = WorkflowStatus.PAUSED
        elif event.event_type == "workflow_resumed":
            _require_payload_keys(payload, frozenset())
            _replay_transition(status, WorkflowStatus.RUNNING)
            status = WorkflowStatus.RUNNING
        elif event.event_type == "attempt_assigned":
            _require_running_status(status, "attempt assigned")
            attempt = _attempt_payload(payload)
            _require_attempt_payload_matches_command(payload, command)
            current = attempts.get(command.task_id or "")
            if current is not None and attempt[2] <= current[2]:
                raise PortabilityInvariantError(
                    "attempt fencing history is not monotonic"
                )
            attempts[command.task_id or ""] = attempt
        elif event.event_type == "attempt_heartbeat":
            _require_running_status(status, "attempt heartbeat")
            attempt = _attempt_payload(payload)
            _require_attempt_payload_matches_command(payload, command)
            current = attempts.get(command.task_id or "")
            if (
                current is None
                or attempt[:3] != current[:3]
                or attempt[3] <= current[3]
            ):
                raise PortabilityInvariantError(
                    "heartbeat does not extend current lease"
                )
            attempts[command.task_id or ""] = attempt
        elif event.event_type in {"effect_committed", "effect_reconciled"}:
            if event.event_type == "effect_committed":
                _require_running_status(status, "effect committed")
                current = attempts.get(command.task_id or "")
                expected = (
                    command.attempt_id,
                    command.worker_id,
                    command.fencing_token,
                )
                if current is None or current[:3] != expected:
                    raise PortabilityInvariantError("effect committed by stale attempt")
            effect_id, payload_hash, provider_receipt_id = _effect_payload(payload)
            _require_effect_payload_matches_command(payload, command)
            receipt = effect_receipt_map.get(effect_id)
            if receipt is None or (
                receipt.command_id != command.command_id
                or receipt.payload_hash != payload_hash
                or receipt.provider_receipt_id != provider_receipt_id
            ):
                raise PortabilityInvariantError("effect event lacks matching receipt")
            if effect_id in effects:
                raise PortabilityInvariantError(
                    "effect identity committed more than once"
                )
            effects[effect_id] = (payload_hash, provider_receipt_id)
        elif event.event_type == "workflow_completed":
            _require_payload_keys(payload, frozenset())
            _replay_transition(status, WorkflowStatus.COMPLETED)
            status = WorkflowStatus.COMPLETED
        elif event.event_type == "workflow_canceled":
            _require_payload_keys(payload, frozenset())
            _replay_transition(status, WorkflowStatus.CANCELED)
            status = WorkflowStatus.CANCELED
    return PortabilitySnapshot(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        workflow_status=status.value,
        graph_revision=graph_revision,
        active_attempts=tuple(
            (task_id, attempt_id, worker_id, token, expiry)
            for task_id, (attempt_id, worker_id, token, expiry) in sorted(
                attempts.items()
            )
        ),
        committed_effects=tuple(
            (effect_id, payload_hash, provider_receipt_id)
            for effect_id, (payload_hash, provider_receipt_id) in sorted(
                effects.items()
            )
        ),
        last_event_sequence=len(events) - 1,
    )


def _history(
    *,
    tenant_id: str,
    workflow_id: str,
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
        graph_revision=graph_revision,
        commands=commands,
        events=events,
        command_receipts=command_receipts,
        effect_receipts=effect_receipts,
        history_hash=portability_history_digest(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=graph_revision,
            commands=commands,
            events=events,
            command_receipts=command_receipts,
            effect_receipts=effect_receipts,
        ),
    )


def _effect_receipt(
    *, command: PortabilityCommand, request_hash: str, provider_receipt_id: str
) -> PortabilityEffectReceipt:
    return PortabilityEffectReceipt(
        effect_id=command.effect_id or "",
        command_id=command.command_id,
        request_hash=request_hash,
        tenant_id=command.tenant_id,
        workflow_id=command.workflow_id,
        graph_revision=command.graph_revision,
        task_id=command.task_id or "",
        attempt_id=command.attempt_id or "",
        worker_id=command.worker_id or "",
        fencing_token=int(command.fencing_token or 0),
        payload_hash=command.payload_hash or "",
        provider_receipt_id=provider_receipt_id,
    )


def _validate_history_header(history: PortabilityHistory) -> None:
    if history.contract_version != PORTABILITY_CONTRACT_VERSION:
        raise PortabilityInvariantError("unsupported portability contract version")
    if type(history.tenant_id) is not str or not history.tenant_id:
        raise PortabilityInvariantError("history tenant_id must be a string")
    if type(history.workflow_id) is not str or not history.workflow_id:
        raise PortabilityInvariantError("history workflow_id must be a string")
    if type(history.graph_revision) is not int or history.graph_revision < 1:
        raise PortabilityInvariantError("history graph_revision must be positive")


def _verify_checkpoint(
    checkpoint: PortabilityCheckpoint,
    history: PortabilityHistory,
    snapshot: PortabilitySnapshot,
) -> None:
    if checkpoint.contract_version != PORTABILITY_CONTRACT_VERSION:
        raise PortabilityInvariantError("unsupported checkpoint contract version")
    if (
        checkpoint.tenant_id != history.tenant_id
        or checkpoint.workflow_id != history.workflow_id
        or checkpoint.graph_revision != history.graph_revision
    ):
        raise PortabilityInvariantError("checkpoint scope does not match history")
    if checkpoint.event_sequence != len(history.events) - 1:
        raise PortabilityInvariantError(
            "checkpoint event cursor does not match history"
        )
    if checkpoint.history_hash != history.history_hash:
        raise PortabilityInvariantError("checkpoint history digest mismatch")
    expected_receipts = tuple(
        receipt.provider_receipt_id for receipt in history.effect_receipts
    )
    if checkpoint.committed_receipt_ids != expected_receipts:
        raise PortabilityInvariantError("checkpoint receipt inventory mismatch")
    if checkpoint.snapshot != snapshot:
        raise PortabilityInvariantError("checkpoint snapshot does not match replay")


def _verify_effect_sink_bindings(
    history: PortabilityHistory, effect_sink: PortabilityEffectSink
) -> None:
    sink_receipts = effect_sink.export_receipts(
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
    )
    if sink_receipts != history.effect_receipts:
        raise PortabilityInvariantError(
            "portable history does not match harness receipt ledger"
        )
    executions = effect_sink.export_executions(
        tenant_id=history.tenant_id,
        workflow_id=history.workflow_id,
    )
    commands = {command.command_id: command for command in history.commands}
    receipts = {receipt.effect_id: receipt for receipt in history.effect_receipts}
    execution_effect_ids: set[str] = set()
    for execution in executions:
        command = execution.command
        effect_id = command.effect_id or ""
        if effect_id in execution_effect_ids:
            raise PortabilityInvariantError("provider execution identity is duplicated")
        execution_effect_ids.add(effect_id)
        matching_commands = tuple(
            candidate
            for candidate in history.commands
            if candidate.operation is PortabilityOperation.COMMIT_EFFECT
            and candidate.effect_id == effect_id
        )
        if (
            command.operation is not PortabilityOperation.COMMIT_EFFECT
            or commands.get(command.command_id) != command
            or matching_commands != (command,)
            or execution.request_hash != portability_command_digest(command)
        ):
            raise PortabilityInvariantError(
                "provider execution lacks exact pending command evidence"
            )
        receipt = receipts.get(effect_id)
        if receipt is not None and receipt != _effect_receipt(
            command=command,
            request_hash=execution.request_hash,
            provider_receipt_id=execution.provider_receipt_id,
        ):
            raise PortabilityInvariantError(
                "provider execution does not match effect receipt"
            )
    if not set(receipts).issubset(execution_effect_ids):
        raise PortabilityInvariantError("effect receipt lacks provider execution")


def _active_attempts(snapshot: PortabilitySnapshot) -> dict[str, AttemptState]:
    return {
        task_id: (attempt_id, worker_id, token, expiry)
        for task_id, attempt_id, worker_id, token, expiry in snapshot.active_attempts
    }


def _event_payload(event: PortabilityEvent) -> dict[str, object]:
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PortabilityInvariantError("event payload is not valid JSON") from exc
    if type(payload) is not dict:
        raise PortabilityInvariantError("event payload must be an object")
    if canonical_event_payload(payload) != event.payload_json:
        raise PortabilityInvariantError("event payload must be canonical")
    return payload


def _attempt_payload(payload: dict[str, object]) -> AttemptState:
    _require_payload_keys(
        payload,
        frozenset(
            {
                "task_id",
                "attempt_id",
                "worker_id",
                "fencing_token",
                "lease_expires_at_tick",
            }
        ),
    )
    return (
        _payload_string(payload, "attempt_id"),
        _payload_string(payload, "worker_id"),
        _payload_integer(payload, "fencing_token"),
        _payload_integer(payload, "lease_expires_at_tick"),
    )


def _effect_payload(payload: dict[str, object]) -> tuple[str, str, str]:
    _require_payload_keys(
        payload,
        frozenset(
            {
                "task_id",
                "attempt_id",
                "worker_id",
                "fencing_token",
                "effect_id",
                "payload_hash",
                "provider_receipt_id",
            }
        ),
    )
    return (
        _payload_string(payload, "effect_id"),
        _payload_string(payload, "payload_hash"),
        _payload_string(payload, "provider_receipt_id"),
    )


def _require_attempt_payload_matches_command(
    payload: dict[str, object], command: PortabilityCommand
) -> None:
    if (
        payload["task_id"] != command.task_id
        or payload["attempt_id"] != command.attempt_id
        or payload["worker_id"] != command.worker_id
        or payload["fencing_token"] != command.fencing_token
        or payload["lease_expires_at_tick"] != command.lease_expires_at_tick
    ):
        raise PortabilityInvariantError("attempt event does not match command")


def _require_effect_payload_matches_command(
    payload: dict[str, object], command: PortabilityCommand
) -> None:
    if (
        payload["task_id"] != command.task_id
        or payload["attempt_id"] != command.attempt_id
        or payload["worker_id"] != command.worker_id
        or payload["fencing_token"] != command.fencing_token
        or payload["effect_id"] != command.effect_id
        or payload["payload_hash"] != command.payload_hash
    ):
        raise PortabilityInvariantError("effect event does not match command")


def _expected_event_types(operation: PortabilityOperation) -> frozenset[str]:
    if operation is PortabilityOperation.COMMIT_EFFECT:
        return frozenset({"effect_committed", "effect_reconciled"})
    return frozenset(
        {
            {
                PortabilityOperation.START_WORKFLOW: "workflow_started",
                PortabilityOperation.PAUSE_WORKFLOW: "workflow_paused",
                PortabilityOperation.RESUME_WORKFLOW: "workflow_resumed",
                PortabilityOperation.ASSIGN_ATTEMPT: "attempt_assigned",
                PortabilityOperation.HEARTBEAT_ATTEMPT: "attempt_heartbeat",
                PortabilityOperation.COMPLETE_WORKFLOW: "workflow_completed",
                PortabilityOperation.CANCEL_WORKFLOW: "workflow_canceled",
            }[operation]
        }
    )


def _require_running(snapshot: PortabilitySnapshot) -> None:
    if snapshot.workflow_status != WorkflowStatus.RUNNING.value:
        raise PortabilityInvariantError("operation requires a running workflow")


def _require_running_status(status: WorkflowStatus, operation: str) -> None:
    if status is not WorkflowStatus.RUNNING:
        raise PortabilityInvariantError(f"{operation} outside running workflow")


def _require_status_transition(
    snapshot: PortabilitySnapshot, target: WorkflowStatus
) -> None:
    _replay_transition(WorkflowStatus(snapshot.workflow_status), target)


def _replay_transition(source: WorkflowStatus, target: WorkflowStatus) -> None:
    try:
        require_workflow_transition(source, target)
    except ValueError as exc:
        raise PortabilityInvariantError(str(exc)) from exc


def _payload_string(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if type(value) is not str or not value:
        raise PortabilityInvariantError(f"event {field_name} must be a string")
    return value


def _payload_integer(payload: dict[str, object], field_name: str) -> int:
    value = payload.get(field_name)
    if type(value) is not int or value < 1:
        raise PortabilityInvariantError(f"event {field_name} must be positive")
    return value


def _require_payload_keys(payload: dict[str, object], expected: frozenset[str]) -> None:
    if frozenset(payload) != expected:
        raise PortabilityInvariantError("event payload fields do not match contract")


__all__ = [
    "InternalKernelAdapter",
    "InternalKernelStore",
    "verify_portability_history",
]
