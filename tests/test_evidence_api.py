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

from shared.db.connection import set_database_path, init_db
from api.main import app
from domain.evidence.types import EvidenceProduct

CLIENT_ID = "test-client"


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "evidence-api.db"
    set_database_path(db_path)
    init_db()
    return TestClient(app)


def test_evidence_analyze_returns_products(client, monkeypatch):
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

    response = client.post(
        "/evidence/analyze", json={"query": "bright room TV", "client_id": CLIENT_ID}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_products"][0]["id"] == "ev-1"
    assert payload["profiles"]
    assert payload["alignment_scores"]


def test_representation_optimize_returns_before_after(client):
    payload = {
        "query": "reduce back pain",
        "client_id": CLIENT_ID,
        "evidence_products": [
            {
                "id": "ev-2",
                "name": "Align Chair",
                "description": "Ergonomic chair with lumbar support.",
                "source": "web",
                "confidence": 0.7,
            }
        ],
    }

    response = client.post("/representation/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["optimized"][0]["before"]
    assert data["optimized"][0]["after"]
    assert data["alignment_deltas"]


def test_recommendation_verify_returns_lift(client):
    payload = {
        "query": "running shoes for joint pain",
        "client_id": CLIENT_ID,
        "evidence_products": [
            {
                "id": "ev-3",
                "name": "StrideFlex Trainer",
                "description": "Running shoes with responsive foam.",
                "source": "web",
                "confidence": 0.65,
            }
        ],
        "optimized": [
            {
                "id": "ev-3",
                "name": "StrideFlex Trainer",
                "before": "Running shoes with responsive foam.",
                "after": "Support longer runs with cushioning that eases joint strain.",
                "capabilities": ["Joint comfort"],
                "outcomes": ["Reduced joint strain"],
                "goals": ["Protect knees"],
            }
        ],
    }

    response = client.post("/recommendation/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "lift" in data
    assert data["predicted"]
    assert data["actual"]
