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
from application.services.agent_runtime.scheduler import AgentRuntimeSchedulerService
from shared.db.connection import init_db, set_database_path


def _create_run(deps, *, client_id: str) -> dict:
    return deps.agent_runs.create_agent_run(
        client_id=client_id,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="running",
    )


def _add_action(deps, *, run_id: str, sequence: int = 1) -> dict:
    return deps.agent_actions.create_agent_action(
        agent_run_id=run_id,
        sequence=sequence,
        status="approved",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        inputs={"experiment_id": "exp-1"},
        outputs={},
        inputs_hash="in",
        outputs_hash=None,
        rationale="test action",
        confidence=0.7,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )


def test_scheduler_run_once_processes_multiple_clients(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-runtime-scheduler-once.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    deps.clients.create_client(client_id="client-b", name="Client B")
    run_a = _create_run(deps, client_id="client-a")
    run_b = _create_run(deps, client_id="client-b")
    _add_action(deps, run_id=run_a["id"])
    _add_action(deps, run_id=run_b["id"])

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **kwargs: {"ok": True},
    )

    scheduler = AgentRuntimeSchedulerService(deps=deps)
    summary = scheduler.run_once(
        user_id="scheduler",
        max_clients=10,
        max_runs_per_client=5,
        max_steps_per_run=2,
    )
    assert summary["clients_considered"] == 2
    assert summary["clients_processed"] == 2
    assert summary["runs_processed_total"] == 2
    assert summary["steps_executed_total"] == 2


def test_scheduler_run_forever_respects_max_cycles(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-runtime-scheduler-loop.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    run = _create_run(deps, client_id="client-a")
    _add_action(deps, run_id=run["id"])

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **kwargs: {"ok": True},
    )

    sleep_calls: list[float] = []
    scheduler = AgentRuntimeSchedulerService(deps=deps)
    result = scheduler.run_forever(
        interval_seconds=1,
        client_id="client-a",
        user_id="scheduler",
        max_runs_per_client=5,
        max_steps_per_run=2,
        max_cycles=2,
        sleep_fn=lambda value: sleep_calls.append(value),
    )
    assert result["cycles_completed"] == 2
    assert len(result["cycle_results"]) == 2
    assert len(sleep_calls) == 1
