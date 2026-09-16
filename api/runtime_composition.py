"""Privileged production composition for governed agent execution."""

from __future__ import annotations

from application.ports.deps import AppDeps
from application.services.agent_runtime.runtime import AgentRuntimeService
from application.services.agent_runtime.worker import AgentRuntimeWorkerService
from application.services.workflow_outcomes.production import (
    PRODUCTION_HOST_AUTHORITY,
    SequentialCompletionCoordinator,
)
from infrastructure.db.workflow.outcome_ledger import SQLiteWorkflowOutcomeLedger


def default_completion_coordinator(deps: AppDeps) -> SequentialCompletionCoordinator:
    """Construct the privileged host boundary outside worker-visible AppDeps."""

    return SequentialCompletionCoordinator(
        deps=deps,
        store=SQLiteWorkflowOutcomeLedger(host_authority=PRODUCTION_HOST_AUTHORITY),
    )


def default_runtime(deps: AppDeps) -> AgentRuntimeService:
    return AgentRuntimeService(
        deps=deps, completion_coordinator=default_completion_coordinator(deps)
    )


def default_worker(deps: AppDeps) -> AgentRuntimeWorkerService:
    return AgentRuntimeWorkerService(
        deps=deps, completion_coordinator=default_completion_coordinator(deps)
    )


__all__ = ["default_completion_coordinator", "default_runtime", "default_worker"]
