from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shared.db.connection import init_db, set_database_path
from api.main import app
import infrastructure.db.catalog.clients as clients_repo


CLIENT_ID = "client-test"
BRAND_ID = "brand-test"
PRODUCT_ID = "product-test"


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "batteries-experiments.db"
    set_database_path(db_path)
    init_db()
    clients_repo.create_client(client_id=CLIENT_ID, name="Client Test")
    clients_repo.create_client(client_id="client-other", name="Client Other")
    clients_repo.create_brand(brand_id=BRAND_ID, client_id=CLIENT_ID, name="Brand Test")
    clients_repo.create_product(
        product_id=PRODUCT_ID, brand_id=BRAND_ID, name="Product Test"
    )
    return TestClient(app)


def test_battery_crud_and_queries(client: TestClient):
    create_response = client.post(
        "/batteries",
        json={
            "client_id": CLIENT_ID,
            "brand_id": BRAND_ID,
            "product_id": PRODUCT_ID,
            "name": "Battery A",
            "purpose": "Baseline coverage",
            "generation_mode": "bottom_up",
        },
    )
    assert create_response.status_code == 200
    battery = create_response.json()["battery"]
    battery_id = battery["id"]
    assert battery["product_id"] == PRODUCT_ID

    list_response = client.get(
        f"/batteries?client_id={CLIENT_ID}&product_id={PRODUCT_ID}"
    )
    assert list_response.status_code == 200
    assert any(item["id"] == battery_id for item in list_response.json()["batteries"])

    get_response = client.get(f"/batteries/{battery_id}?client_id={CLIENT_ID}")
    assert get_response.status_code == 200
    assert get_response.json()["battery"]["id"] == battery_id

    update_response = client.patch(
        f"/batteries/{battery_id}",
        json={"client_id": CLIENT_ID, "status": "active"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["battery"]["status"] == "active"

    query_response = client.post(
        f"/batteries/{battery_id}/queries",
        json={
            "client_id": CLIENT_ID,
            "query_text": "best trail running vest for rain",
            "query_type": "coverage",
            "constraints": {"price_max": 120},
        },
    )
    assert query_response.status_code == 200
    query_id = query_response.json()["query"]["id"]

    list_queries = client.get(f"/batteries/{battery_id}/queries?client_id={CLIENT_ID}")
    assert list_queries.status_code == 200
    assert any(item["id"] == query_id for item in list_queries.json()["queries"])

    update_query = client.patch(
        f"/batteries/{battery_id}/queries/{query_id}",
        json={"client_id": CLIENT_ID, "enabled": False, "weight": 0.5},
    )
    assert update_query.status_code == 200
    assert update_query.json()["query"]["enabled"] is False

    generate_response = client.post(
        f"/batteries/{battery_id}/generate",
        json={
            "client_id": CLIENT_ID,
            "source": "top_down",
            "seed_queries": [
                "best running vest for rain",
                "lightweight vest for trail runs",
            ],
            "limit": 5,
        },
    )
    assert generate_response.status_code == 200
    assert len(generate_response.json()["queries"]) >= 1

    eval_summary = client.get(
        f"/batteries/{battery_id}/eval-summary?client_id={CLIENT_ID}"
    )
    assert eval_summary.status_code == 200
    assert "summary" in eval_summary.json()

    ontology_updates = client.get(
        f"/batteries/{battery_id}/ontology-updates?client_id={CLIENT_ID}"
    )
    assert ontology_updates.status_code == 200
    assert "updates" in ontology_updates.json()


def test_bottom_up_generation_requires_category_clarification(client: TestClient):
    battery_response = client.post(
        "/batteries",
        json={
            "client_id": CLIENT_ID,
            "product_id": PRODUCT_ID,
            "name": "Battery Clarify",
            "generation_mode": "bottom_up",
        },
    )
    battery_id = battery_response.json()["battery"]["id"]
    generate_response = client.post(
        f"/batteries/{battery_id}/generate",
        json={
            "client_id": CLIENT_ID,
            "source": "bottom_up",
            "limit": 5,
        },
    )
    assert generate_response.status_code == 200
    payload = generate_response.json()
    assert payload["queries"] == []
    assert payload["report"]["clarification_required"] is True
    assert isinstance(payload["report"]["clarification_prompt"], str)


def test_experiments_and_variants(client: TestClient):
    battery_response = client.post(
        "/batteries",
        json={
            "client_id": CLIENT_ID,
            "product_id": PRODUCT_ID,
            "name": "Battery B",
            "generation_mode": "top_down",
        },
    )
    battery_id = battery_response.json()["battery"]["id"]
    client.post(
        f"/batteries/{battery_id}/queries",
        json={
            "client_id": CLIENT_ID,
            "query_text": "best training shoe for achilles pain",
            "query_type": "coverage",
        },
    )

    create_experiment = client.post(
        "/experiments",
        json={
            "client_id": CLIENT_ID,
            "brand_id": BRAND_ID,
            "product_id": PRODUCT_ID,
            "battery_id": battery_id,
            "name": "Experiment 1",
            "hypothesis": {"metric": "win_rate", "direction": "increase"},
        },
    )
    assert create_experiment.status_code == 200
    experiment = create_experiment.json()["experiment"]
    experiment_id = experiment["id"]
    assert experiment["battery_id"] == battery_id

    list_experiments = client.get(
        f"/experiments?client_id={CLIENT_ID}&product_id={PRODUCT_ID}"
    )
    assert list_experiments.status_code == 200
    assert any(
        item["id"] == experiment_id for item in list_experiments.json()["experiments"]
    )

    add_variant = client.post(
        f"/experiments/{experiment_id}/variants",
        json={
            "client_id": CLIENT_ID,
            "label": "A",
            "type": "copy",
            "payload": {"description": "Rewritten copy"},
        },
    )
    assert add_variant.status_code == 200
    variant_id = add_variant.json()["variant"]["id"]

    list_variants = client.get(
        f"/experiments/{experiment_id}/variants?client_id={CLIENT_ID}"
    )
    assert list_variants.status_code == 200
    assert any(item["id"] == variant_id for item in list_variants.json()["variants"])

    update_experiment = client.patch(
        f"/experiments/{experiment_id}",
        json={"client_id": CLIENT_ID, "status": "running"},
    )
    assert update_experiment.status_code == 200
    assert update_experiment.json()["experiment"]["status"] == "running"

    run_response = client.post(
        f"/experiments/{experiment_id}/run",
        json={"client_id": CLIENT_ID, "variant_id": variant_id},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["experiment_id"] == experiment_id
    assert payload["variant_id"] == variant_id
    assert payload["metrics"]["total_runs"] >= 0

    runs_response = client.get(
        f"/experiments/{experiment_id}/runs?client_id={CLIENT_ID}"
    )
    assert runs_response.status_code == 200
    assert isinstance(runs_response.json()["runs"], list)

    metrics_response = client.get(
        f"/experiments/{experiment_id}/metrics?client_id={CLIENT_ID}"
    )
    assert metrics_response.status_code == 200
    assert isinstance(metrics_response.json()["metrics"], list)

    validation_response = client.post(
        f"/experiments/{experiment_id}/validations",
        json={
            "client_id": CLIENT_ID,
            "variant_id": variant_id,
            "platform": "chatgpt",
            "query_text": "best training shoe for achilles pain",
            "observed_products": ["Product Test"],
            "observed_winner_variant_id": variant_id,
        },
    )
    assert validation_response.status_code == 200
    assert "validation" in validation_response.json()
    assert "summary" in validation_response.json()

    summary_response = client.get(
        f"/experiments/{experiment_id}/validation-summary?client_id={CLIENT_ID}"
    )
    assert summary_response.status_code == 200
    assert "summary" in summary_response.json()

    accuracy_response = client.get(
        f"/brands/{BRAND_ID}/prediction-accuracy?client_id={CLIENT_ID}"
    )
    assert accuracy_response.status_code == 200
    assert "summary" in accuracy_response.json()


def test_variant_routes_enforce_experiment_client_scope(client: TestClient):
    create_experiment = client.post(
        "/experiments",
        json={
            "client_id": CLIENT_ID,
            "brand_id": BRAND_ID,
            "product_id": PRODUCT_ID,
            "name": "Scoped Experiment",
        },
    )
    assert create_experiment.status_code == 200
    experiment_id = create_experiment.json()["experiment"]["id"]

    wrong_scope_add = client.post(
        f"/experiments/{experiment_id}/variants",
        json={
            "client_id": "client-other",
            "label": "X",
            "type": "copy",
            "payload": {"description": "Cross-tenant variant"},
        },
    )
    assert wrong_scope_add.status_code == 404

    wrong_scope_list = client.get(
        f"/experiments/{experiment_id}/variants?client_id=client-other"
    )
    assert wrong_scope_list.status_code == 404
