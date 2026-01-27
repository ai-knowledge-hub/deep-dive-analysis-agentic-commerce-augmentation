from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(
                generate_content=lambda **_: types.SimpleNamespace(text="")
            )

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from shared.db.connection import init_db, set_database_path
from api.main import app
from infrastructure.db import clients as clients_repo

CLIENT_ID = "test-client"


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "simulation-api.db"
    set_database_path(db_path)
    init_db()
    return TestClient(app)


def test_simulation_run_returns_result(client: TestClient):
    payload = {
        "query": "running vest",
        "client_id": CLIENT_ID,
        "products": [
            {
                "id": "sim-1",
                "name": "Trail Runner Vest",
                "description": "Lightweight vest for long runs with breathable mesh.",
                "source": "web",
                "confidence": 0.6,
            },
            {
                "id": "sim-2",
                "name": "City Runner Vest",
                "description": "Reflective vest for urban running with zip pockets.",
                "source": "web",
                "confidence": 0.5,
            },
        ],
    }

    response = client.post("/simulation/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"]
    assert data["result"]["goals"]
    assert data["result"]["scores"]


def test_simulation_optimize_and_retest(client: TestClient):
    run_payload = {
        "query": "reduce back pain",
        "client_id": CLIENT_ID,
        "products": [
            {
                "id": "sim-3",
                "name": "Support Chair",
                "description": "Ergonomic chair with lumbar support.",
                "source": "web",
                "confidence": 0.7,
            }
        ],
    }
    run_response = client.post("/simulation/run", json=run_payload)
    run_id = run_response.json()["run_id"]

    optimize_response = client.post(
        "/simulation/optimize",
        json={"run_id": run_id, "product_id": "sim-3", "client_id": CLIENT_ID},
    )
    assert optimize_response.status_code == 200
    optimized = optimize_response.json()["optimized"]
    assert optimized["before"]
    assert optimized["after"]

    retest_response = client.post(
        "/simulation/retest",
        json={
            "run_id": run_id,
            "client_id": CLIENT_ID,
            "optimized_products": [
                {
                    "id": "sim-3",
                    "name": "Support Chair",
                    "description": optimized["after"],
                    "source": "web",
                    "confidence": 0.7,
                }
            ],
        },
    )
    assert retest_response.status_code == 200
    assert retest_response.json()["result"]["scores"]


def test_simulation_attach_to_product(client: TestClient):
    run_payload = {
        "query": "bright room TV",
        "client_id": CLIENT_ID,
        "products": [
            {
                "id": "sim-4",
                "name": "Glare Guard TV",
                "description": "High brightness panel with anti-glare coating.",
                "source": "web",
                "confidence": 0.7,
            }
        ],
    }
    run_response = client.post("/simulation/run", json=run_payload)
    run_id = run_response.json()["run_id"]

    brand = clients_repo.create_brand(
        brand_id="brand-tv", client_id=CLIENT_ID, name="TV Brand"
    )
    clients_repo.create_product(
        product_id="prod-tv-1", brand_id=brand["id"], name="Glare Guard TV"
    )

    attach_response = client.post(
        "/simulation/attach",
        json={
            "run_id": run_id,
            "client_id": CLIENT_ID,
            "brand_id": "brand-tv",
            "product_id": "prod-tv-1",
        },
    )
    assert attach_response.status_code == 200
    data = attach_response.json()
    assert data["product_id"] == "prod-tv-1"
    assert data["brand_id"] == "brand-tv"

    list_response = client.get(f"/simulation/runs?client_id={CLIENT_ID}&limit=5")
    assert list_response.status_code == 200
    runs = list_response.json()["runs"]
    assert any(
        run["id"] == run_id and run.get("product_id") == "prod-tv-1" for run in runs
    )


def test_simulation_run_autopicks_competitors_from_catalog(client: TestClient):
    # Create "our" client and product (selected by product_id)
    clients_repo.create_client(
        client_id="client-underarmour", name="Under Armour", metadata={"demo": True}
    )
    our_brand = clients_repo.create_brand(
        brand_id="brand-ua", client_id="client-underarmour", name="Under Armour"
    )
    clients_repo.create_product(
        product_id="ua-vest-1",
        brand_id=our_brand["id"],
        name="UA Rain Running Vest",
        description="Packable running vest for light rain and wind.",
        metadata={"source": "catalog", "offer_url": "https://example.com/ua-vest"},
    )

    # Create competitor client + product that should be picked by LIKE query
    clients_repo.create_client(
        client_id="client-nike", name="Nike", metadata={"demo": True}
    )
    comp_brand = clients_repo.create_brand(
        brand_id="brand-nike", client_id="client-nike", name="Nike"
    )
    clients_repo.create_product(
        product_id="nike-vest-1",
        brand_id=comp_brand["id"],
        name="Nike Running Vest",
        description="running vest with reflective details and zip pockets.",
        metadata={"source": "catalog", "offer_url": "https://example.com/nike-vest"},
    )

    payload = {
        "query": "running vest",
        "client_id": "client-underarmour",
        "products": [],
        "product_id": "ua-vest-1",
        "auto_competitors": True,
        "competitor_client_ids": ["client-nike"],
    }

    response = client.post("/simulation/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"]
    product_ids = [score["product_id"] for score in data["result"]["scores"]]
    assert "ua-vest-1" in product_ids
    assert "nike-vest-1" in product_ids
