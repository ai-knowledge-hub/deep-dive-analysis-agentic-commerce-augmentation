"""Full private control-state fence for lifecycle and historical recovery admission."""

from __future__ import annotations

from typing import Any

from application.services.conversation.operator_snapshot import (
    build_operator_snapshot,
    MAX_ACTIONS,
)
from domain.workflow.operator_commands import canonical_digest


def build_control_snapshot(**kwargs: Any) -> dict[str, Any]:
    """Fence full control state privately; display only the established safe view."""
    completion_reader = kwargs["completion_reader"]
    completion = None

    def read_completion(**scope: Any) -> Any:
        nonlocal completion
        completion = completion_reader(**scope)
        return completion

    snapshot = build_operator_snapshot(
        **{**kwargs, "completion_reader": read_completion}
    )
    deps = kwargs["deps"]
    run_id, tenant_id = kwargs["run_id"], kwargs["tenant_id"]
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=MAX_ACTIONS + 1
    )
    membership = next(
        (
            row
            for row in deps.clients.list_client_users(client_id=tenant_id)
            if row["user_id"] == kwargs["principal_id"].removeprefix("human:")
        ),
        None,
    )
    control = {
        "run": run,
        "actions": actions,
        "membership": membership,
        "completion": completion,
        "completion_verified": completion is not None,
        "approvals": [],
        "effects": [],
        "validation": [],
    }
    for action in actions:
        scope = {
            "tenant_id": tenant_id,
            "workflow_id": run_id,
            "action_id": action["id"],
        }
        control["approvals"].append(
            deps.approval_ledger.get_current_approval_for_action(**scope)
        )
        control["effects"].append(
            deps.approval_ledger.get_effect_execution_for_action(**scope)
        )
    for job in snapshot["validation_jobs"]:
        control["validation"].append(
            {
                "job": deps.validation_jobs.get_job(
                    job_id=job["id"], client_id=tenant_id
                ),
                "result": deps.validation_results.get_latest_for_job(job_id=job["id"]),
            }
        )
    digest = canonical_digest(
        {"snapshot_digest": snapshot["snapshot_digest"], "control": control}
    )
    return {
        **snapshot,
        "snapshot_digest": digest,
        "authority_fence": digest,
        "completion_verified": control["completion_verified"],
    }
