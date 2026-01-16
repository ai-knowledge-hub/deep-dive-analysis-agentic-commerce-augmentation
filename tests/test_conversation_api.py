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

    class GenerateContentConfig:
        def __init__(self, temperature: float = 0.7, max_output_tokens: int = 2048):
            self.temperature = temperature
            self.max_output_tokens = max_output_tokens
            self.tools = None

    class FunctionDeclaration:
        def __init__(
            self,
            name: str,
            description: str | None = None,
            parameters: dict | None = None,
        ):
            self.name = name
            self.description = description
            self.parameters = parameters

    class Tool:
        def __init__(
            self, function_declarations: list[FunctionDeclaration] | None = None
        ):
            self.function_declarations = function_declarations or []

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from modules.values.domain import ClarificationState
from db.connection import set_database_path, init_db
from api.main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "api-memory.db"
    set_database_path(db_path)
    init_db()
    return TestClient(app)


def test_start_endpoint_returns_clarification(client, monkeypatch):
    class DummyValuesAgent:
        def start(self, query, metadata):
            state = ClarificationState(query=query)
            state.add_turn("user", query)
            state.add_turn("agent", "What matters most about this goal?")
            return state

        def continue_dialogue(self, state, message):
            return state

    monkeypatch.setattr("api.routes.conversation.VALUES_AGENT", DummyValuesAgent())

    response = client.post(
        "/conversation/start", json={"opening_message": "Help me focus"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["clarification"] == "What matters most about this goal?"
    assert data["values_state"]["ready_for_products"] is False
    assert data["values_state"]["turns"][-1]["speaker"] == "agent"


def _configure_full_pipeline(monkeypatch):
    def fake_handle(manager, message, metadata):
        state = ClarificationState(
            query=message, ready_for_products=True, extracted_goals=["Stay energized"]
        )
        manager.record_goal("Stay energized")
        return state, None

    class DummyIntentAgent:
        def detect_intent(self, utterance, manager=None):
            return {"label": "workspace_upgrade", "confidence": 0.9, "domain": "career"}

    class DummyCommerceAgent:
        def build_plan(self, intent, goals, context=None):
            products = [
                {
                    "id": "p1",
                    "name": "Focus Chair",
                    "capabilities_enabled": ["Posture"],
                    "confidence": 0.8,
                    "source": "mock",
                    "reasoning": f"Supports {goals[0]}",
                }
            ]
            return {
                "query": "workspace focus kit",
                "products": products,
                "product_explanations": [
                    {
                        "id": "p1",
                        "name": "Focus Chair",
                        "reasoning": f"Supports {goals[0]}",
                        "capabilities_enabled": ["Posture"],
                        "confidence": 0.8,
                    }
                ],
                "clarifications": ["We prioritized posture support."],
                "empowerment": {"goal_alignment": {"score": 0.75}},
                "data_quality": {"average_confidence": 0.8},
            }

    class DummyGuard:
        def check(self, rationale, clarifications, products):
            return {"status": "ok", "flags": []}

    class DummyExplain:
        def explain(self, products):
            return "Recommended Focus Chair for posture."

    class DummyReflection:
        def reflect(self, plan):
            return "Captured empowerment metrics."

    monkeypatch.setattr("api.routes.conversation._handle_values_dialogue", fake_handle)
    monkeypatch.setattr("api.routes.conversation.INTENT_AGENT", DummyIntentAgent())
    monkeypatch.setattr("api.routes.conversation.COMMERCE_AGENT", DummyCommerceAgent())
    monkeypatch.setattr("api.routes.conversation.AUTONOMY_GUARD", DummyGuard())
    monkeypatch.setattr("api.routes.conversation.EXPLAIN_AGENT", DummyExplain())
    monkeypatch.setattr("api.routes.conversation.REFLECTION_AGENT", DummyReflection())


def _configure_research_pipeline(monkeypatch):
    def fake_handle(manager, message, metadata):
        state = ClarificationState(
            query=message, ready_for_products=True, extracted_goals=["Verify data"]
        )
        manager.record_goal("Verify data")
        return state, None

    class DummyIntentAgent:
        def detect_intent(self, utterance, manager=None):
            return {"label": "workspace_upgrade", "confidence": 0.4, "domain": "career"}

    class DummyCommerceAgent:
        def build_plan(self, intent, goals, context=None):
            products = [
                {
                    "id": "p1",
                    "name": "Low Confidence Chair",
                    "capabilities_enabled": ["Posture"],
                    "confidence": 0.3,
                    "source": "mock",
                    "reasoning": "Uncertain match",
                }
            ]
            return {
                "query": "workspace chair",
                "products": products,
                "product_explanations": [
                    {
                        "id": "p1",
                        "name": "Low Confidence Chair",
                        "reasoning": "Uncertain match",
                        "capabilities_enabled": ["Posture"],
                        "confidence": 0.3,
                    }
                ],
                "clarifications": ["Low confidence data."],
                "empowerment": {"goal_alignment": {"score": 0.25}},
                "data_quality": {"average_confidence": 0.4},
            }

    class DummyGuard:
        def check(self, rationale, clarifications, products):
            return {"status": "needs_review", "flags": clarifications}

    class DummyExplain:
        def explain(self, products):
            return "Low confidence catalog results."

    class DummyReflection:
        def reflect(self, plan):
            return "Research suggested."

    def fake_research(query, goals, context):
        return {"query": query, "goals": goals, "summary": "stub research"}

    monkeypatch.setattr("api.routes.conversation._handle_values_dialogue", fake_handle)
    monkeypatch.setattr("api.routes.conversation.INTENT_AGENT", DummyIntentAgent())
    monkeypatch.setattr("api.routes.conversation.COMMERCE_AGENT", DummyCommerceAgent())
    monkeypatch.setattr("api.routes.conversation.AUTONOMY_GUARD", DummyGuard())
    monkeypatch.setattr("api.routes.conversation.EXPLAIN_AGENT", DummyExplain())
    monkeypatch.setattr("api.routes.conversation.REFLECTION_AGENT", DummyReflection())
    monkeypatch.setattr("api.routes.conversation.run_research", fake_research)


def test_start_endpoint_runs_full_pipeline(client, monkeypatch):
    _configure_full_pipeline(monkeypatch)

    response = client.post(
        "/conversation/start",
        json={"opening_message": "Focus setup", "user_id": "tester"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["intent"]["label"] == "workspace_upgrade"
    assert data["plan"]["products"][0]["reasoning"] == "Supports Stay energized"
    assert data["guardrails"]["status"] == "ok"
    assert data["explanation"] == "Recommended Focus Chair for posture."
    assert data["reflection"] == "Captured empowerment metrics."
    assert data["product_explanations"][0]["reasoning"] == "Supports Stay energized"
    assert data["values_state"]["ready_for_products"] is True


def test_get_session_snapshot_returns_latest(client, monkeypatch):
    _configure_full_pipeline(monkeypatch)

    start = client.post(
        "/conversation/start",
        json={"opening_message": "Need focus", "user_id": "snapshot-user"},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    snapshot = client.get(
        f"/conversation/{session_id}", params={"user_id": "snapshot-user"}
    )
    assert snapshot.status_code == 200
    data = snapshot.json()
    assert data["session_id"] == session_id
    assert "snapshot" in data
    assert data["snapshot"]["session"]["id"] == session_id
    assert data["snapshot"]["turns"], "turns should include prior conversation"


def test_research_fallback_returns_payload(client, monkeypatch):
    _configure_research_pipeline(monkeypatch)

    response = client.post(
        "/conversation/start",
        json={"opening_message": "Need a chair", "user_id": "research-user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["research"]
    assert data["research"]["query"] == "workspace chair"
    assert "Verify data" in data["research"]["goals"]
