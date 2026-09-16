"""Test-only host helper for completing a governed sequential run."""

from api.composition import default_deps
from api.runtime_composition import default_completion_coordinator


def complete_governed_run(run_id: str) -> None:
    deps = default_deps()
    action = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=1)[0]
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"],
        status="executed",
        outputs={"status": "completed-by-test-host"},
    )
    lock_token = f"test-completion:{run_id}"
    assert deps.agent_runs.acquire_run_lock(
        run_id=run_id, lock_token=lock_token, ttl_seconds=30
    )
    deps.agent_runs.update_agent_run(run_id=run_id, status="running")
    default_completion_coordinator(deps).synchronize_run(
        run_id=run_id, lock_token=lock_token
    )


__all__ = ["complete_governed_run"]
