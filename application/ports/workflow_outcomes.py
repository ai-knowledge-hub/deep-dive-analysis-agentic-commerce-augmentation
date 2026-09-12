"""Port for durable workflow evidence and completion artifacts."""

from __future__ import annotations

from typing import Any, Protocol

from domain.workflow.outcomes import (
    AuthoritativeTaskDefinition,
    CompletionAuthoritySnapshot,
    CompletionCriteria,
    CompletionDecision,
    EvidenceRecord,
    TaskResult,
)


class WorkflowOutcomeLedgerStore(Protocol):
    def append_evidence(
        self,
        *,
        command: dict[str, Any],
        evidence: EvidenceRecord,
        request_hash: str,
    ) -> dict[str, Any]: ...

    def append_task_result(
        self,
        *,
        command: dict[str, Any],
        result: TaskResult,
        request_hash: str,
    ) -> dict[str, Any]: ...

    def publish_completion_contract(
        self,
        *,
        command: dict[str, Any],
        criteria: CompletionCriteria,
        task_definitions: tuple[AuthoritativeTaskDefinition, ...],
        request_hash: str,
    ) -> dict[str, Any]: ...

    def commit_authority_snapshot(
        self,
        *,
        command: dict[str, Any],
        snapshot_id: str,
        snapshot: CompletionAuthoritySnapshot,
        issued_at: str,
        request_hash: str,
    ) -> dict[str, Any]: ...

    def commit_completion_decision(
        self,
        *,
        command: dict[str, Any],
        decision: CompletionDecision,
        snapshot_id: str,
        result_bindings: tuple[tuple[str, str], ...],
        evidence_bindings: tuple[tuple[str, str], ...],
        request_hash: str,
    ) -> dict[str, Any]: ...

    def get_evidence(
        self, *, tenant_id: str, workflow_id: str, evidence_id: str
    ) -> dict[str, Any] | None: ...

    def get_task_result(
        self, *, tenant_id: str, workflow_id: str, result_id: str
    ) -> dict[str, Any] | None: ...

    def get_task_result_by_digest(
        self, *, tenant_id: str, workflow_id: str, result_digest: str
    ) -> dict[str, Any] | None: ...

    def list_accepted_task_results(
        self, *, tenant_id: str, workflow_id: str, graph_revision: int
    ) -> list[dict[str, Any]]: ...

    def get_completion_contract(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        criteria_id: str,
        criteria_hash: str | None = None,
    ) -> dict[str, Any] | None: ...

    def get_authority_snapshot(
        self, *, tenant_id: str, workflow_id: str, snapshot_id: str
    ) -> dict[str, Any] | None: ...

    def get_completion_decision(
        self, *, tenant_id: str, workflow_id: str, decision_id: str
    ) -> dict[str, Any] | None: ...

    def load_evaluation_bundle(
        self, *, tenant_id: str, workflow_id: str, decision_id: str
    ) -> dict[str, Any] | None: ...


__all__ = ["WorkflowOutcomeLedgerStore"]
