"""Safe production creation boundary for completion-governed runs."""

from __future__ import annotations

from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.runs import (
    AgentRunPlanError,
    create_agent_run_with_initial_plan,
)


def create_governed_agent_run_with_initial_plan(
    *,
    deps: AppDeps,
    completion_coordinator: Any,
    release_to_planned: bool = True,
    **run_kwargs: Any,
) -> dict[str, Any]:
    """Create a production plan behind a non-runnable governance barrier."""

    requested_status = str(run_kwargs.pop("status", "planned") or "planned")
    if requested_status != "planned":
        raise AgentRunPlanError("governed production runs must start as planned")
    run = create_agent_run_with_initial_plan(
        deps=deps, status="planning", **run_kwargs
    )
    try:
        governed = completion_coordinator.activate_run(run_id=str(run["id"]))
        if governed.get("completion_authority_required") is not True:
            raise AgentRunPlanError(
                "governed production runs require at least one planned task"
            )
    except Exception:
        deps.agent_runs.update_agent_run(
            run_id=str(run["id"]), status="failed", error="completion_governance_failed"
        )
        raise
    if not release_to_planned:
        return governed
    activated = deps.agent_runs.update_agent_run(run_id=str(run["id"]), status="planned")
    return activated or governed


__all__ = ["create_governed_agent_run_with_initial_plan"]
