from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

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
from api.main import app
from api.routes import external_agent_jobs as external_jobs_route
from api.utils.principals import build_agent_principal_token
from infrastructure.db.agent.external_agent_jobs import (
    create_external_agent_job as persist_external_agent_job,
    get_external_agent_job_idempotency_reservation,
    release_linked_external_agent_run,
)
from infrastructure.db.core.connection import get_connection
from shared.config.env import get_settings
from shared.db.connection import init_db, set_database_path


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_unlinked_run_stays_non_runnable_across_cleanup_outcomes(
    tmp_path, monkeypatch, cleanup_fails
):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    get_settings.cache_clear()
    set_database_path(tmp_path / "external-agent-governance-failure.db")
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    app.dependency_overrides[external_jobs_route._deps] = lambda: deps
    token = build_agent_principal_token(
        principal_id="agent-ext-failure",
        client_id="client-a",
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=[
            "external_agent_jobs:write",
            "tool:experiment.run_variant",
            "skill:optimize-product-representation",
        ],
    )
    original_update = deps.agent_runs.update_agent_run
    scheduler_observations = []

    def fail_after_observing_barrier(**_):
        scheduler_observations.append(
            deps.agent_runs.list_runnable_agent_runs(client_id="client-a", limit=10)
        )
        if cleanup_fails:
            deps.agent_runs.update_agent_run = lambda **__: (_ for _ in ()).throw(
                RuntimeError("simulated cleanup failure")
            )
        raise RuntimeError("simulated job write failure")

    monkeypatch.setattr(
        external_jobs_route, "create_external_agent_job", fail_after_observing_barrier
    )

    with pytest.raises(RuntimeError, match="simulated job write failure"):
        try:
            TestClient(app).post(
                "/external-agent/jobs",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "idempotency_key": "post-governance-failure",
                    "tool_id": "experiment.run_variant",
                },
            )
        finally:
            app.dependency_overrides.clear()

    run = deps.agent_runs.list_agent_runs(client_id="client-a", limit=1)[0]
    assert scheduler_observations == [[]]
    assert run["status"] == ("planning" if cleanup_fails else "canceled")
    assert deps.agent_runs.list_runnable_agent_runs(client_id="client-a", limit=10) == []
    assert get_connection().execute(
        "SELECT 1 FROM workflow_completion_governance WHERE workflow_id = ?",
        (run["id"],),
    ).fetchone()
    assert (
        get_external_agent_job_idempotency_reservation(
            client_id="client-a",
            principal_id="agent-ext-failure",
            idempotency_key="post-governance-failure",
        )
        is None
    )

    deps.agent_runs.update_agent_run = original_update
    monkeypatch.setattr(
        external_jobs_route, "create_external_agent_job", persist_external_agent_job
    )
    app.dependency_overrides[external_jobs_route._deps] = lambda: deps
    retried = TestClient(app).post(
        "/external-agent/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idempotency_key": "post-governance-failure",
            "tool_id": "experiment.run_variant",
        },
    )
    app.dependency_overrides.clear()
    assert retried.status_code == 200
    assert retried.json()["run"]["id"] != run["id"]
    assert retried.json()["run"]["status"] == "planned"


@pytest.mark.parametrize(
    ("identity_column", "substituted_value"),
    [
        ("principal_id", "agent-ext-substituted"),
        ("principal_type", "internal_agent"),
        ("agent_profile_id", "substituted-profile"),
    ],
)
def test_publication_rejects_job_run_identity_substitution(
    tmp_path, monkeypatch, identity_column, substituted_value
):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    get_settings.cache_clear()
    set_database_path(tmp_path / f"external-agent-{identity_column}-substitution.db")
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    app.dependency_overrides[external_jobs_route._deps] = lambda: deps
    token = build_agent_principal_token(
        principal_id="agent-ext-owner",
        client_id="client-a",
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=[
            "external_agent_jobs:write",
            "tool:experiment.run_variant",
            "skill:optimize-product-representation",
        ],
    )
    try:
        created = TestClient(app).post(
            "/external-agent/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "idempotency_key": f"{identity_column}-substitution",
                "tool_id": "experiment.run_variant",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert created.status_code == 200
    payload = created.json()
    run_id = payload["run"]["id"]
    job_id = payload["job"]["id"]

    # Model an alternate/internal writer substituting one authoritative run
    # identity after durable job creation but before publication/replay.
    get_connection().execute(
        f"UPDATE agent_runs SET status = 'planning', {identity_column} = ? WHERE id = ?",
        (substituted_value, run_id),
    )
    get_connection().commit()

    assert not release_linked_external_agent_run(
        job_id=job_id,
        run_id=run_id,
        client_id="client-a",
        principal_id="agent-ext-owner",
    )
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id="client-a")
    assert run is not None
    assert run["status"] == "planning"
    assert deps.agent_runs.list_runnable_agent_runs(client_id="client-a", limit=10) == []
