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

from api.main import app
from infrastructure.db import analytics_events as analytics_repo
from infrastructure.db import clients as clients_repo
from shared.db.connection import init_db, set_database_path


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "memory-loop.db"
    set_database_path(db_path)
    init_db()
    clients_repo.create_client(client_id="client-a", name="Client A")
    clients_repo.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    clients_repo.create_product(
        product_id="product-a",
        brand_id="brand-a",
        name="Runner Shoe A",
        description="lightweight trainer for road running",
        metadata={"vertical": "sports_apparel"},
    )
    clients_repo.create_client(client_id="client-b", name="Client B")
    return TestClient(app)


def test_memory_distill_and_retrieve_tenant_isolation(client: TestClient):
    first = client.post(
        "/memory/distill",
        json={
            "client_id": "client-a",
            "brand_id": "brand-a",
            "product_id": "product-a",
            "vertical": "sports_apparel",
            "artifact_type": "query_pattern",
            "payload": {
                "query_template": "best cushioned running shoes for tendon support"
            },
            "quality_score": 0.9,
            "support_count": 4,
            "source": "manual",
        },
    )
    assert first.status_code == 200
    artifact_id = first.json()["artifact"]["id"]

    list_a = client.get(
        "/memory/artifacts?client_id=client-a&artifact_type=query_pattern&vertical=sports_apparel"
    )
    assert list_a.status_code == 200
    artifacts = list_a.json()["artifacts"]
    assert any(item["id"] == artifact_id for item in artifacts)

    list_b = client.get(
        "/memory/artifacts?client_id=client-b&artifact_type=query_pattern&vertical=sports_apparel"
    )
    assert list_b.status_code == 200
    assert list_b.json()["artifacts"] == []


def test_query_generation_includes_memory_provenance(client: TestClient):
    artifact = client.post(
        "/memory/distill",
        json={
            "client_id": "client-a",
            "brand_id": "brand-a",
            "product_id": "product-a",
            "vertical": "sports_apparel",
            "artifact_type": "query_pattern",
            "payload": {"query_template": "stability running shoes for flat feet"},
            "quality_score": 0.92,
            "support_count": 5,
            "source": "manual",
        },
    )
    assert artifact.status_code == 200
    artifact_id = artifact.json()["artifact"]["id"]

    battery = client.post(
        "/batteries",
        json={
            "client_id": "client-a",
            "brand_id": "brand-a",
            "product_id": "product-a",
            "name": "Memory battery",
            "purpose": "provenance check",
            "generation_mode": "bottom_up",
        },
    )
    assert battery.status_code == 200
    battery_id = battery.json()["battery"]["id"]

    generated = client.post(
        f"/batteries/{battery_id}/generate",
        json={
            "client_id": "client-a",
            "source": "bottom_up",
            "use_llm": False,
            "persist": False,
            "seed_features": ["cushioning", "stability support"],
            "seed_use_cases": ["daily road running"],
            "limit": 5,
        },
    )
    assert generated.status_code == 200
    report = generated.json()["report"]
    assert artifact_id in (report.get("memory_artifact_ids") or [])

    events = analytics_repo.list_events(client_id="client-a", limit=20)
    match = next(
        (
            event
            for event in events
            if event.get("event_type") == "query_generation_eval"
            and (event.get("metadata") or {}).get("battery_id") == battery_id
        ),
        None,
    )
    assert match is not None
    report_meta = (match.get("metadata") or {}).get("report") or {}
    assert artifact_id in (report_meta.get("memory_artifact_ids") or [])
