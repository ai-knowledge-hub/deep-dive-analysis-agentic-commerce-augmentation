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

from db.connection import init_db, set_database_path
from api.main import app

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
