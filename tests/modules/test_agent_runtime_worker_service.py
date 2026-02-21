from __future__ import annotations

import sys
import types

if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")
    genai_pkg.Client = lambda *args, **kwargs: None
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from api.composition import default_deps
from application.services.agent_runtime.worker import AgentRuntimeWorkerService
from shared.db.connection import init_db, set_database_path


def _create_client(deps) -> None:
    deps.clients.create_client(client_id="client-a", name="Client A")


def _create_run(deps, *, status: str = "running", run_mode: str = "auto_execute_safe"):
    return deps.agent_runs.create_agent_run(
        client_id="client-a",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={"max_actions": 5},
        approval_policy={},
        requires_approval=True,
        run_mode=run_mode,
        state="battery_ready",
        status=status,
    )


def _add_action(deps, *, run_id: str, status: str = "approved", sequence: int = 1):
    return deps.agent_actions.create_agent_action(
        agent_run_id=run_id,
        sequence=sequence,
        status=status,
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        inputs={"experiment_id": "exp-1"},
        outputs={},
        inputs_hash="in",
        outputs_hash=None,
        rationale="test",
        confidence=0.8,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )


def test_worker_tick_executes_approved_actions(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-worker-tick.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    _create_client(deps)
    run = _create_run(deps)
    _add_action(deps, run_id=run["id"])

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **kwargs: {"ok": True},
    )

    worker = AgentRuntimeWorkerService(deps=deps)
    summary = worker.tick_client(
        client_id="client-a",
        user_id="worker",
        max_runs=5,
        max_steps_per_run=3,
    )
    assert summary["runs_processed"] == 1
    assert summary["steps_executed_total"] == 1
    action_rows = deps.agent_actions.list_agent_actions(
        agent_run_id=run["id"], limit=10
    )
    assert action_rows[0]["status"] == "executed"


def test_worker_tick_skips_plan_only_runs(tmp_path):
    db_path = tmp_path / "agent-worker-plan-only.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    _create_client(deps)
    run = _create_run(deps, run_mode="plan_only", status="planned")
    _add_action(deps, run_id=run["id"])

    worker = AgentRuntimeWorkerService(deps=deps)
    summary = worker.tick_client(
        client_id="client-a",
        user_id="worker",
        max_runs=5,
        max_steps_per_run=3,
    )
    assert summary["runs_considered"] == 0
    assert summary["runs_processed"] == 0
