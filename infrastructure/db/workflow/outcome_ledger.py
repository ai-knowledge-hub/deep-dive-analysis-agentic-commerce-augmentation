"""Host-authority-bound SQLite adapter for the workflow outcome ledger."""

from __future__ import annotations

from typing import Any

from domain.workflow.outcome_authority import HostCompletionAuthority
from infrastructure.db.core.connection import get_connection
from infrastructure.db.workflow import outcome_reads, outcome_writes


class SQLiteWorkflowOutcomeLedger:
    """Expose privileged writes only through an independently bound policy."""

    def __init__(self, *, host_authority: HostCompletionAuthority) -> None:
        if type(host_authority) is not HostCompletionAuthority:
            raise TypeError("host_authority must be exact HostCompletionAuthority")
        self._host_authority = host_authority

    def append_evidence(self, **kwargs: Any) -> dict[str, Any]:
        return outcome_writes.append_evidence(
            get_connection(), host_authority=self._host_authority, **kwargs
        )

    def append_task_result(self, **kwargs: Any) -> dict[str, Any]:
        return outcome_writes.append_task_result(
            get_connection(), host_authority=self._host_authority, **kwargs
        )

    def publish_completion_contract(self, **kwargs: Any) -> dict[str, Any]:
        return outcome_writes.publish_completion_contract(
            get_connection(), host_authority=self._host_authority, **kwargs
        )

    def commit_authority_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return outcome_writes.commit_authority_snapshot(
            get_connection(), host_authority=self._host_authority, **kwargs
        )

    def commit_completion_decision(self, **kwargs: Any) -> dict[str, Any]:
        return outcome_writes.commit_completion_decision(
            get_connection(), host_authority=self._host_authority, **kwargs
        )

    def get_evidence(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_evidence_locked(get_connection(), **kwargs)

    def get_task_result(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_task_result_locked(get_connection(), **kwargs)

    def get_task_result_by_digest(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_task_result_by_digest_locked(
            get_connection(), **kwargs
        )

    def list_accepted_task_results(self, **kwargs: Any) -> list[dict[str, Any]]:
        return outcome_reads.list_accepted_task_results_locked(
            get_connection(), **kwargs
        )

    def get_completion_contract(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_completion_contract_locked(get_connection(), **kwargs)

    def get_authority_snapshot(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_authority_snapshot_locked(get_connection(), **kwargs)

    def get_completion_decision(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_completion_decision_locked(get_connection(), **kwargs)

    def load_evaluation_bundle(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.load_evaluation_bundle_locked(get_connection(), **kwargs)


__all__ = ["SQLiteWorkflowOutcomeLedger"]
