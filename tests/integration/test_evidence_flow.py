from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

# Stub google.genai so importing the Gemini client doesn't require the SDK.
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
from db.connection import init_db, set_database_path
from domain.evidence.types import EvidenceProduct

CLIENT_ID = "test-client"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "evidence-flow.db"
    set_database_path(db_path)
    init_db()

    def fake_retrieve(query: str, max_items: int = 5):
        return [
            EvidenceProduct(
                id="ev-1",
                name="BrightRoom TV",
                description="High brightness panel for daylight viewing.",
                source="web",
                url="https://example.com/brightroom-tv",
                confidence=0.6,
            )
        ]

    monkeypatch.setattr("api.routes.evidence.retrieve", fake_retrieve)
    return TestClient(app)


def test_evidence_flow_end_to_end(client):
    analyze = client.post(
        "/evidence/analyze",
        json={"query": "TV for bright room", "client_id": CLIENT_ID},
    )
    assert analyze.status_code == 200
    payload = analyze.json()
    assert payload["evidence_products"]

    optimize = client.post(
        "/representation/optimize",
        json={
            "query": "TV for bright room",
            "evidence_products": payload["evidence_products"],
            "client_id": CLIENT_ID,
        },
    )
    assert optimize.status_code == 200
    optimized = optimize.json()
    assert optimized["optimized"]

    verify = client.post(
        "/recommendation/verify",
        json={
            "query": "TV for bright room",
            "evidence_products": payload["evidence_products"],
            "optimized": optimized["optimized"],
            "client_id": CLIENT_ID,
        },
    )
    assert verify.status_code == 200
    verified = verify.json()
    assert "lift" in verified
    assert verified["predicted"]
