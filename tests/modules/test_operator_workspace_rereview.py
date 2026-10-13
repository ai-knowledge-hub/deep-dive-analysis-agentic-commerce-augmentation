"""Multi-tenant membership, executable prerequisites and long private history."""

from types import SimpleNamespace

import pytest

from tests.modules.test_operator_workspace import (
    workspace_api as workspace_api,
    experiment,
    prepare,
    confirm,
    counts,
    workspace_assertion,
)
from tests.test_operator_conversation_api import TENANT, USER, _headers
from infrastructure.db.core.connection import get_connection
from api.utils.principals import ensure_principal, _assert_principal_is_active


@pytest.mark.parametrize("authentication", ["bearer", "bff"])
def test_valid_human_membership_survives_repeated_tenant_switches(
    workspace_api, authentication
):
    client, deps = workspace_api
    other = "other-member-tenant"
    deps.clients.ensure_client(other)
    deps.clients.add_client_user(client_id=other, user_id=USER, role="operator")
    sessions = {}
    for tenant in [TENANT, other, TENANT, other]:
        headers = (
            _headers(client_id=tenant)
            if authentication == "bearer"
            else workspace_assertion("list", "list", client_id=tenant)
        )
        listing = client.get(
            "/conversation/operator/workspaces",
            params={"client_id": tenant},
            headers=headers,
        )
        assert listing.status_code == 200, listing.text
        # A signed identity and membership do not confer access to another tenant's session.
        if tenant not in sessions:
            headers = (
                _headers(client_id=tenant)
                if authentication == "bearer"
                else workspace_assertion("new", "message", client_id=tenant)
            )
            response = client.post(
                "/conversation/operator/workspaces/message",
                headers=headers,
                json={"client_id": tenant, "message": "Improve performance"},
            )
            assert response.status_code == 200, response.text
            sessions[tenant] = response.json()["session_id"]
        assert all(
            row["tenant_id"] == tenant for row in listing.json()["conversations"]
        )
    for tenant, session in sessions.items():
        wrong = other if tenant == TENANT else TENANT
        headers = (
            _headers(client_id=wrong)
            if authentication == "bearer"
            else workspace_assertion(session, "read", client_id=wrong)
        )
        assert (
            client.get(
                f"/conversation/operator/workspaces/{session}",
                params={"client_id": wrong},
                headers=headers,
            ).status_code
            == 404
        )
    # Creation in both memberships also rechecks authority under the final lock.
    experiment(deps)
    deps.clients.create_brand(
        brand_id="other-brand", client_id=other, name="Other brand"
    )
    deps.clients.create_product(
        product_id="other-product", brand_id="other-brand", name="Other product"
    )
    battery = deps.query_batteries.create_battery(
        client_id=other, product_id="other-product", name="Other queries"
    )
    deps.query_batteries.add_query(
        battery_id=battery["id"], query_text="Compare products"
    )
    exp = deps.experiments.create_experiment(
        client_id=other,
        product_id="other-product",
        brand_id="other-brand",
        battery_id=battery["id"],
        name="Other experiment",
    )
    deps.experiments.add_variant(
        experiment_id=exp["id"],
        client_id=other,
        label="Control",
        variant_type="baseline",
        payload={"role": "control"},
    )
    proposals = {}
    for tenant in [TENANT, other]:
        headers = (
            _headers(client_id=tenant)
            if authentication == "bearer"
            else workspace_assertion(sessions[tenant], "message", client_id=tenant)
        )
        response = client.post(
            "/conversation/operator/workspaces/message",
            headers=headers,
            json={
                "client_id": tenant,
                "session_id": sessions[tenant],
                "message": "Improve performance",
            },
        )
        assert response.status_code == 200, response.text
        proposals[tenant] = response.json()["proposal"]
    for tenant in [TENANT, other]:
        proposal = proposals[tenant]
        headers = (
            _headers(client_id=tenant, scopes=["agent_runs:read", "agent_runs:write"])
            if authentication == "bearer"
            else workspace_assertion(
                sessions[tenant],
                "confirm",
                client_id=tenant,
                proposal_id=proposal["proposal_id"],
                proposal_digest=proposal["proposal_digest"],
            )
        )
        result = client.post(
            f"/conversation/operator/workspaces/{sessions[tenant]}/proposals/{proposal['proposal_id']}/confirm",
            headers=headers,
            json={"client_id": tenant, "proposal_digest": proposal["proposal_digest"]},
        )
        assert result.status_code == 200, result.text
        assert (
            deps.agent_runs.get_agent_run(run_id=result.json()["run_id"])["client_id"]
            == tenant
        )
    conn = get_connection()
    conn.execute(
        "DELETE FROM client_users WHERE client_id=? AND user_id=?", (other, USER)
    )
    conn.commit()
    assert (
        client.get(
            "/conversation/operator/workspaces",
            params={"client_id": other},
            headers=_headers(client_id=other),
        ).status_code
        == 403
    )
    conn.execute(
        "UPDATE principals SET status='disabled' WHERE id=?", (f"human:{USER}",)
    )
    conn.commit()
    assert (
        client.get(
            "/conversation/operator/workspaces",
            params={"client_id": TENANT},
            headers=_headers(),
        ).status_code
        == 401
    )


def test_nonhuman_registry_tenant_and_principal_type_guards_remain(workspace_api):
    ensure_principal(
        principal_id="agent-bound", principal_type="external_agent", tenant_id=TENANT
    )
    with pytest.raises(Exception, match="403"):
        _assert_principal_is_active(
            principal_id="agent-bound",
            principal_type="external_agent",
            tenant_id="another",
        )
    with pytest.raises(Exception, match="403"):
        _assert_principal_is_active(
            principal_id="agent-bound", principal_type="human", tenant_id=TENANT
        )


def test_preparation_requires_control_before_creating_execution(workspace_api):
    client, deps = workspace_api
    exp = experiment(deps, control=False)
    deps.experiments.add_variant(
        experiment_id=exp["id"],
        client_id=TENANT,
        label="Candidate",
        variant_type="variant",
        payload={"role": "candidate"},
    )
    before = counts()
    response = prepare(client)
    assert response.status_code == 409 and "control variant" in response.text
    assert counts() == before
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_run_creation_proposals")
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("change", ["delete", "remove_role", "replace", "final_lock"])
def test_confirmation_rechecks_control_and_pins_its_identity(
    workspace_api, monkeypatch, change
):
    client, deps = workspace_api
    exp = experiment(deps)
    prepared = prepare(client).json()
    control_id = deps.experiments.list_variants(exp["id"])[0]["id"]
    before = counts()
    conn = get_connection()

    def remove():
        get_connection().execute(
            "DELETE FROM experiment_variants WHERE id=?", (control_id,)
        )

    if change == "final_lock":
        commit = deps.operator_workspace.commit_creation

        def raced(**kwargs):
            authorize = kwargs["authorize"]

            def changed():
                authorize()
                remove()

            return commit(**{**kwargs, "authorize": changed})

        monkeypatch.setattr(deps.operator_workspace, "commit_creation", raced)
    elif change == "remove_role":
        conn.execute(
            "UPDATE experiment_variants SET label='Candidate',payload_json='{}' WHERE id=?",
            (control_id,),
        )
        conn.commit()
    else:
        remove()
        conn.commit()
        if change == "replace":
            deps.experiments.add_variant(
                experiment_id=exp["id"],
                client_id=TENANT,
                label="New control",
                variant_type="baseline",
                payload={"role": "control"},
            )
    response = confirm(client, prepared)
    assert response.status_code == 409, response.text
    assert counts() == before
    assert not conn.in_transaction


@pytest.mark.parametrize("kind", ["role", "label"])
def test_accepted_control_is_resolved_by_real_baseline_capability(
    workspace_api, monkeypatch, kind
):
    from application.services.agent_runtime.capabilities import (
        execute_capability,
        CapabilityContext,
    )
    from application.services.agent_runtime.capabilities.executor import (
        ExperimentRunner,
    )

    client, deps = workspace_api
    exp = experiment(deps, control=False)
    control = deps.experiments.add_variant(
        experiment_id=exp["id"],
        client_id=TENANT,
        label="Original" if kind == "role" else "CONTROL baseline",
        variant_type="baseline",
        payload={"role": "control"} if kind == "role" else {},
    )
    prepared = prepare(client)
    assert prepared.status_code == 200, prepared.text
    assert confirm(client, prepared.json()).status_code == 200
    calls = []

    def run(self, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(metrics={"metric_id": "baseline-proof"})

    monkeypatch.setattr(ExperimentRunner, "run_experiment", run)
    # Real capability dispatch and target resolution, stubbing only the runner/provider work.
    result = execute_capability(
        deps=deps,
        context=CapabilityContext(client_id=TENANT, user_id=USER),
        capability_name="run_control_baseline",
        inputs={"experiment_id": exp["id"]},
    )
    assert result["variant_id"] == control["id"]
    assert calls[0]["variant_id"] == control["id"] and calls[0]["client_id"] == TENANT


def test_latest_history_and_older_pages_preserve_provenance_with_new_inserts(
    workspace_api,
):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    confirm(client, prepared)
    sid = prepared["session_id"]
    conn = get_connection()
    # Same timestamps deliberately exercise deterministic ordering, not clock precision.
    conn.executemany(
        "INSERT INTO turns(session_id,speaker,content,metadata_json) VALUES(?, 'user', ?, '{}')",
        [(sid, f"padding {i}") for i in range(502)],
    )
    conn.commit()
    answer = prepare(client, session_id=sid, message="Explain this run").json()[
        "response"
    ]
    original_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM turns WHERE session_id=? ORDER BY id", (sid,)
        )
    ]
    latest = client.get(
        f"/conversation/operator/workspaces/{sid}", headers=_headers()
    ).json()
    assert [turn["id"] for turn in latest["turns"]] == original_ids[-500:]
    saved = next(turn for turn in latest["turns"] if turn["id"] == answer["turn_id"])
    assert saved["metadata"]["operator_response"]["evidence"] == answer["evidence"]
    assert saved["metadata"]["operator_response"]["snapshot"] == answer["snapshot"]
    assert latest["turns_has_more"] and latest["turns_before_id"] == original_ids[-500]
    # Concurrent newer turns must not shift an older page's cursor.
    deps.turns.add_turn(session_id=sid, speaker="user", content="after paging")
    older = client.get(
        f"/conversation/operator/workspaces/{sid}",
        headers=_headers(),
        params={"before_turn_id": latest["turns_before_id"]},
    ).json()
    assert [turn["id"] for turn in older["turns"]] == original_ids[:-500]
    assert not older["turns_has_more"] and older["turns_before_id"] is None
    assert len(set(t["id"] for t in older["turns"] + latest["turns"])) == len(
        original_ids
    )
    deps.users.ensure_user("other-reader")
    deps.clients.add_client_user(
        client_id=TENANT, user_id="other-reader", role="operator"
    )
    denied = client.get(
        f"/conversation/operator/workspaces/{sid}",
        headers=_headers(principal_id="human:other-reader"),
        params={"before_turn_id": latest["turns_before_id"]},
    )
    assert denied.status_code == 404


@pytest.mark.parametrize("cursor", [0, -1, "bad", 2**100])
def test_invalid_history_cursor_is_rejected(workspace_api, cursor):
    client, _ = workspace_api
    assert (
        client.get(
            "/conversation/operator/workspaces/not-a-session",
            headers=_headers(),
            params={"before_turn_id": cursor},
        ).status_code
        == 422
    )
