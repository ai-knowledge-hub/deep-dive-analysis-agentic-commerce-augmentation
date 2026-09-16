"""Immutable compare-and-swap authority for completion projection commits."""

from __future__ import annotations

import re
from dataclasses import dataclass

from domain.workflow.outcomes import OutcomeContractError


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class CompletionProjectionFence:
    """Exact run/action snapshot observed before completion evaluation."""

    tenant_id: str
    workflow_id: str
    active_graph_revision: int
    run_status: str
    run_state: str
    active_lock_token: str | None
    action_projection_digest: str

    def __post_init__(self) -> None:
        for field_name in ("tenant_id", "workflow_id", "run_status", "run_state"):
            value = getattr(self, field_name)
            if type(value) is not str or not value or value != value.strip():
                raise OutcomeContractError(
                    f"{field_name} must be a non-empty canonical exact string"
                )
        if (
            type(self.active_graph_revision) is not int
            or self.active_graph_revision < 1
        ):
            raise OutcomeContractError(
                "active_graph_revision must be an exact positive integer"
            )
        if (
            type(self.action_projection_digest) is not str
            or _DIGEST_PATTERN.fullmatch(self.action_projection_digest) is None
        ):
            raise OutcomeContractError(
                "action_projection_digest must be a lowercase SHA-256 digest"
            )
        if self.active_lock_token is not None and (
            type(self.active_lock_token) is not str
            or not self.active_lock_token
            or self.active_lock_token != self.active_lock_token.strip()
        ):
            raise OutcomeContractError(
                "active_lock_token must be a canonical exact string when present"
            )


@dataclass(frozen=True)
class TaskAttemptAuthority:
    """Host-read identity and live lease fencing one result validation."""

    tenant_id: str
    workflow_id: str
    graph_revision: int
    task_id: str
    attempt_id: str
    assignment_id: str | None
    producer_principal_id: str
    action_id: str
    active_lock_token: str

    def __post_init__(self) -> None:
        for field_name in (
            "tenant_id",
            "workflow_id",
            "task_id",
            "attempt_id",
            "producer_principal_id",
            "action_id",
            "active_lock_token",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value or value != value.strip():
                raise OutcomeContractError(
                    f"{field_name} must be a non-empty canonical exact string"
                )
        if type(self.graph_revision) is not int or self.graph_revision < 1:
            raise OutcomeContractError("graph_revision must be a positive exact int")
        if self.assignment_id is not None and (
            type(self.assignment_id) is not str
            or not self.assignment_id
            or self.assignment_id != self.assignment_id.strip()
        ):
            raise OutcomeContractError("assignment_id must be canonical when present")


__all__ = ["CompletionProjectionFence", "TaskAttemptAuthority"]
