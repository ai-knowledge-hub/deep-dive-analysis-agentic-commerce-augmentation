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

from shared.db.connection import init_db, set_database_path
from api.main import app

CLIENT_ID = "test-client"
USER_ID = "user-abc"


def _fake_embed_batch(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        seed = sum(ord(ch) for ch in str(text))
        vectors.append([((seed + i * 31) % 1000) / 1000.0 for i in range(16)])
    return vectors


@pytest.fixture(autouse=True)
def _fast_llm_and_embeddings(monkeypatch):
    monkeypatch.setattr(
        "api.composition.generate",
        lambda prompt, system_instruction=None, provider=None: "stubbed llm response",
    )
    monkeypatch.setattr(
        "api.composition.classify_intent",
        lambda query, **kwargs: {
            "primary_goal": "shopping",
            "secondary_goals": ["compare products"],
            "confidence": 0.9,
            "source": "stub",
        },
    )
    monkeypatch.setattr(
        "infrastructure.alignment.goal_alignment_gateway.embeddings_provider.embed_batch",
        _fake_embed_batch,
    )
    monkeypatch.setattr(
        "infrastructure.alignment.goal_alignment_gateway._embedding_provider_name",
        lambda: "stub",
    )
    monkeypatch.setattr(
        "infrastructure.simulation.gap_analysis.embedding_available",
        lambda: False,
    )
    monkeypatch.setattr("api.composition.validate_ucp_candidate", lambda *args, **kwargs: [])
    monkeypatch.setattr("api.composition.validate_acp_candidate", lambda *args, **kwargs: [])


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "replay.db"
    set_database_path(db_path)
    init_db()
    return TestClient(app)


def test_replay_records_list_and_get(client: TestClient):
    run = client.post(
        "/simulation/run",
        json={
            "query": "bright room TV",
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "products": [
                {
                    "id": "p1",
                    "name": "GlareGuard TV",
                    "description": "High brightness panel for daylight viewing.",
                    "source": "web",
                    "confidence": 0.7,
                }
            ],
        },
    )
    assert run.status_code == 200
    replay_id = (run.json().get("result") or {}).get("_replay_id")
    assert replay_id

    listed = client.get(
        f"/replay/records?client_id={CLIENT_ID}&user_id={USER_ID}&entity_type=simulation_run&limit=10"
    )
    assert listed.status_code == 200
    records = listed.json()["records"]
    assert any(item["id"] == replay_id for item in records)

    fetched = client.get(
        f"/replay/records/{replay_id}?client_id={CLIENT_ID}&user_id={USER_ID}"
    )
    assert fetched.status_code == 200
    record = fetched.json()["record"]
    assert record["id"] == replay_id
    assert record["run_type"] == "simulation.run"
