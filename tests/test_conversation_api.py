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

from domain.values.types import GoalClarificationState
from db.connection import set_database_path, init_db
from api.main import app

CLIENT_ID = "test-client"


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "api-memory.db"
    set_database_path(db_path)
    init_db()
    return TestClient(app)


def test_start_endpoint_returns_clarification(client, monkeypatch):
    class DummyGoalAgent:
        def start(self, query, metadata):
            state = GoalClarificationState(query=query)
            state.add_turn("user", query)
            state.add_turn("agent", "What matters most about this goal?")
            return state

        def continue_dialogue(self, state, message):
            return state

    class DummyIntentAgent:
        def detect_intent(self, utterance, manager=None):
            return {"primary_goal": "unknown", "confidence": 0.2}

    class DummyCommerceAgent:
        def build_plan(self, intent, goals, context=None):
            return {
                "query": "focus support",
                "products": [],
                "clarifications": [],
                "alignment": {"goal_alignment": {"score": 0.0}},
                "data_quality": {"average_confidence": 0.0},
            }

    class DummyExplain:
        def explain(self, products):
            return ""

    monkeypatch.setattr("api.routes.conversation.GOAL_AGENT", DummyGoalAgent())
    monkeypatch.setattr("api.routes.conversation.INTENT_AGENT", DummyIntentAgent())
    monkeypatch.setattr("api.routes.conversation.COMMERCE_AGENT", DummyCommerceAgent())
    monkeypatch.setattr("api.routes.conversation.EXPLAIN_AGENT", DummyExplain())

    response = client.post(
        "/conversation/start",
        json={"opening_message": "Help me focus", "client_id": CLIENT_ID},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["clarification"] == "What matters most about this goal?"
    assert data["goal_state"]["ready_for_products"] is False
    assert data["goal_state"]["turns"][-1]["speaker"] == "agent"


def _configure_full_pipeline(monkeypatch):
    class DummyGoalAgent:
        def start(self, query, metadata):
            return GoalClarificationState(
                query=query, ready_for_products=True, extracted_goals=["Stay energized"]
            )

        def continue_dialogue(self, state, message):
            return state

    class DummyIntentAgent:
        def detect_intent(self, utterance, manager=None):
            return {
                "primary_goal": "workspace upgrade",
                "confidence": 0.9,
                "domain": "career",
            }

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
                "alignment": {"goal_alignment": {"score": 0.75}},
                "data_quality": {"average_confidence": 0.8},
            }

    class DummyExplain:
        def explain(self, products):
            return "Recommended Focus Chair for posture."

    monkeypatch.setattr("api.routes.conversation.GOAL_AGENT", DummyGoalAgent())
    monkeypatch.setattr("api.routes.conversation.INTENT_AGENT", DummyIntentAgent())
    monkeypatch.setattr("api.routes.conversation.COMMERCE_AGENT", DummyCommerceAgent())
    monkeypatch.setattr("api.routes.conversation.EXPLAIN_AGENT", DummyExplain())


def _configure_research_pipeline(monkeypatch):
    class DummyGoalAgent:
        def start(self, query, metadata):
            return GoalClarificationState(
                query=query, ready_for_products=True, extracted_goals=["Verify data"]
            )

        def continue_dialogue(self, state, message):
            return state

    class DummyIntentAgent:
        def detect_intent(self, utterance, manager=None):
            return {
                "primary_goal": "workspace upgrade",
                "confidence": 0.9,
                "domain": "career",
            }

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
                "alignment": {"goal_alignment": {"score": 0.25}},
                "data_quality": {"average_confidence": 0.4},
            }

    class DummyExplain:
        def explain(self, products):
            return "Low confidence catalog results."

    def fake_research(query, goals, context):
        return {"query": query, "goals": goals, "summary": "stub research"}

    monkeypatch.setattr("api.routes.conversation.GOAL_AGENT", DummyGoalAgent())
    monkeypatch.setattr("api.routes.conversation.INTENT_AGENT", DummyIntentAgent())
    monkeypatch.setattr("api.routes.conversation.COMMERCE_AGENT", DummyCommerceAgent())
    monkeypatch.setattr("api.routes.conversation.EXPLAIN_AGENT", DummyExplain())
    monkeypatch.setattr("api.routes.conversation.run_research", fake_research)


def test_start_endpoint_runs_full_pipeline(client, monkeypatch):
    _configure_full_pipeline(monkeypatch)

    response = client.post(
        "/conversation/start",
        json={
            "opening_message": "Focus setup",
            "user_id": "tester",
            "client_id": CLIENT_ID,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["intent"]["primary_goal"] == "workspace upgrade"
    assert data["plan"]["products"][0]["reasoning"] == "Supports Stay energized"
    assert data["explanation"] == "Recommended Focus Chair for posture."
    assert data["product_explanations"][0]["reasoning"] == "Supports Stay energized"
    assert data["goal_state"]["ready_for_products"] is True
    assert data["intentionality_profiles"]
    assert data["baseline_alignment"] is not None


def test_products_enrich_endpoint_returns_profile_and_alignment(client, monkeypatch):
    from domain.commerce.types import Product

    def mock_search(query: str):
        return [
            Product(
                id="p1",
                name="Focus Chair",
                price=199.0,
                tags=["chair"],
                confidence=0.9,
                source="mock",
                capabilities_enabled=["Reduce back strain"],
                description="Reduce back strain during long sessions.",
            )
        ]

    class DummyClassifier:
        def classify(self, text, context=None):
            return type(
                "Result",
                (),
                {"to_dict": lambda self: {"primary_goal": "workspace upgrade"}},
            )()

    monkeypatch.setattr("api.routes.products.product_search.search", mock_search)
    monkeypatch.setattr("api.routes.products.HybridIntentClassifier", DummyClassifier)

    response = client.post(
        "/products/enrich",
        json={
            "product_id": "p1",
            "query": "Need a better chair",
            "client_id": CLIENT_ID,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["id"] == "p1"
    assert payload["profile"]["product_id"] == "p1"
    assert "aligned_goals" in payload["alignment"]
    assert "baseline_score" in payload["alignment"]


def test_products_profile_endpoint_returns_profile(client, monkeypatch):
    from domain.commerce.types import Product

    def mock_search(query: str):
        return [
            Product(
                id="p2",
                name="Desk Lamp",
                price=49.0,
                tags=["lamp"],
                confidence=0.8,
                source="mock",
                capabilities_enabled=["Reduce eye strain"],
                description="Soft lighting for focus.",
            )
        ]

    monkeypatch.setattr("api.routes.products.product_search.search", mock_search)

    response = client.post(
        "/products/profile", json={"product_id": "p2", "client_id": CLIENT_ID}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["product_id"] == "p2"


def test_products_profile_endpoint_requires_product_id(client):
    response = client.post("/products/profile", json={})
    assert response.status_code == 422


def test_products_align_endpoint_returns_alignment(client, monkeypatch):
    from domain.commerce.types import Product

    def mock_search(query: str):
        return [
            Product(
                id="p3",
                name="Monitor Stand",
                price=29.0,
                tags=["stand"],
                confidence=0.75,
                source="mock",
                capabilities_enabled=["Improve posture"],
                description="Raises monitor height for better posture.",
            )
        ]

    class DummyClassifier:
        def classify(self, text, context=None):
            return type(
                "Result",
                (),
                {"to_dict": lambda self: {"primary_goal": "workspace upgrade"}},
            )()

    monkeypatch.setattr("api.routes.products.product_search.search", mock_search)
    monkeypatch.setattr("api.routes.products.HybridIntentClassifier", DummyClassifier)

    response = client.post(
        "/products/align", json={"query": "Need a stand", "client_id": CLIENT_ID}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["primary_goal"] == "workspace upgrade"
    assert "aligned_goals" in payload["alignment"]
    assert "baseline_score" in payload["alignment"]


def test_products_align_endpoint_requires_query(client):
    response = client.post("/products/align", json={})
    assert response.status_code == 422


def test_intent_infer_endpoint_returns_intent(client, monkeypatch):
    class DummyClassifier:
        def classify(self, text, context=None):
            return type(
                "Result",
                (),
                {
                    "to_dict": lambda self: {
                        "primary_goal": "workspace upgrade",
                        "confidence": 0.9,
                    }
                },
            )()

    monkeypatch.setattr("api.routes.intent.HybridIntentClassifier", DummyClassifier)

    response = client.post(
        "/intent/infer", json={"query": "Need a better desk", "client_id": CLIENT_ID}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["primary_goal"] == "workspace upgrade"


def test_intent_infer_endpoint_requires_query(client):
    response = client.post("/intent/infer", json={})
    assert response.status_code == 422


def test_get_session_snapshot_returns_latest(client, monkeypatch):
    _configure_full_pipeline(monkeypatch)

    start = client.post(
        "/conversation/start",
        json={
            "opening_message": "Need focus",
            "user_id": "snapshot-user",
            "client_id": CLIENT_ID,
        },
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    snapshot = client.get(
        f"/conversation/{session_id}",
        params={"user_id": "snapshot-user", "client_id": CLIENT_ID},
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
        json={
            "opening_message": "Need a chair",
            "user_id": "research-user",
            "client_id": CLIENT_ID,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["research"]
    assert data["research"]["query"] == "workspace chair"
    assert "Verify data" in data["research"]["goals"]
    assert data["plan"]["research_results"] is not None
