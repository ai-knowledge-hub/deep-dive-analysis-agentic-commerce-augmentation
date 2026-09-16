"""Host-authority-bound SQLite adapter for the workflow outcome ledger."""

from __future__ import annotations

from typing import Any

from domain.workflow.outcome_authority import HostCompletionAuthority
from infrastructure.db.core.connection import get_connection
import infrastructure.db.workflow.outcome_reads as outcome_reads
import infrastructure.db.workflow.outcome_writes as outcome_writes
import infrastructure.db.workflow.outcome_attempts as outcome_attempts
import infrastructure.db.workflow.outcome_projection_ops as outcome_projection_ops


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

    def register_sequential_attempt_authority(self, **kwargs: Any) -> dict[str, str]:
        return outcome_attempts.register_sequential_attempt_authority(
            get_connection(), **kwargs
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

    def get_task_attempt_authority(self, **kwargs: Any):
        return outcome_reads.get_task_attempt_authority_locked(
            get_connection(), **kwargs
        )

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

    def get_active_completion_contract(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_active_completion_contract_locked(
            get_connection(), **kwargs
        )

    def get_authority_snapshot(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_authority_snapshot_locked(get_connection(), **kwargs)

    def get_completion_decision(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_completion_decision_locked(get_connection(), **kwargs)

    def get_completion_projection_fence(self, **kwargs: Any):
        return outcome_reads.get_completion_projection_fence_locked(
            get_connection(), **kwargs
        )

    def get_completion_projection(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.get_completion_projection_locked(
            get_connection(), **kwargs
        )

    def resolve_completion_event_sequence(self, **kwargs: Any) -> int:
        return outcome_reads.resolve_completion_event_sequence_locked(
            get_connection(), **kwargs
        )

    def load_evaluation_bundle(self, **kwargs: Any) -> dict[str, Any] | None:
        return outcome_reads.load_evaluation_bundle_locked(get_connection(), **kwargs)

    def get_completion_operational_view(self, **kwargs: Any) -> dict[str, Any] | None:
        conn = get_connection()
        owns_transaction = not conn.in_transaction
        if owns_transaction:
            conn.execute("BEGIN")
        try:
            view = outcome_projection_ops.get_completion_operational_view(
                conn, **kwargs
            )
            if owns_transaction:
                conn.commit()
            return view
        except Exception:
            if owns_transaction:
                conn.rollback()
            raise

    def repair_completion_projection(self, **kwargs: Any) -> dict[str, Any]:
        return outcome_projection_ops.repair_completion_projection(
            get_connection(), **kwargs
        )


__all__ = ["SQLiteWorkflowOutcomeLedger"]
