from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

# Stub google.genai so the Gemini client import succeeds without the SDK.
if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(generate_content=lambda **_: types.SimpleNamespace(text=""))

    class GenerateContentConfig:
        def __init__(self, temperature: float = 0.7, max_output_tokens: int = 2048):
            self.temperature = temperature
            self.max_output_tokens = max_output_tokens
            self.tools = None

    class FunctionDeclaration:
        def __init__(self, name: str, description: str | None = None, parameters: dict | None = None):
            self.name = name
            self.description = description
            self.parameters = parameters

    class Tool:
        def __init__(self, function_declarations: list[FunctionDeclaration] | None = None):
            self.function_declarations = function_declarations or []

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from llm.agents.values import ClarificationState
from db.connection import set_database_path, init_db
from api.main import app


@pytest.fixture()
def integration_client(tmp_path, monkeypatch):
    db_path = tmp_path / "integration.db"
    set_database_path(db_path)
    init_db()

    def fake_handle(manager, message, metadata):
        state = ClarificationState(query=message, ready_for_products=True, extracted_goals=["Stay energized"])
        manager.record_goal("Stay energized")
        manager.update_state(clarification_state=state.to_dict())
        return state, None

    class DummyIntentAgent:
        def detect_intent(self, utterance):
            return {"label": "workspace_upgrade", "confidence": 0.9, "domain": "career"}

    class DummyCommerceAgent:
        def build_plan(self, intent, goals):
            return {
                "query": "workspace focus kit",
                "products": [
                    {
                        "id": "p1",
                        "name": "Focus Chair",
                        "capabilities_enabled": ["Posture"],
                        "confidence": 0.8,
                        "source": "mock",
                    }
                ],
                "clarifications": ["We prioritized posture support."],
                "empowerment": {"goal_alignment": {"score": 0.75}},
                "data_quality": {"average_confidence": 0.8},
            }

    def fake_reason(goals, products):
        return [dict(product, reasoning=f"Supports {goals[0]}") for product in products]

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
    monkeypatch.setattr("api.routes.conversation.reason_about_products", fake_reason)
    monkeypatch.setattr("api.routes.conversation.AUTONOMY_GUARD", DummyGuard())
    monkeypatch.setattr("api.routes.conversation.EXPLAIN_AGENT", DummyExplain())
    monkeypatch.setattr("api.routes.conversation.REFLECTION_AGENT", DummyReflection())

    return TestClient(app)


def test_full_conversation_flow(integration_client):
    start_response = integration_client.post(
        "/conversation/start",
        json={"opening_message": "Need focus", "user_id": "integration-user"},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    session_id = start_payload["session_id"]
    assert start_payload["guardrails"]["status"] == "ok"
    assert start_payload["plan"]["products"][0]["reasoning"] == "Supports Stay energized"

    message_response = integration_client.post(
        f"/conversation/{session_id}/message",
        json={"message": "continue", "user_id": "integration-user"},
    )
    assert message_response.status_code == 200
    message_payload = message_response.json()

    assert message_payload["intent"]["label"] == "workspace_upgrade"
    assert message_payload["plan"]["products"][0]["reasoning"] == "Supports Stay energized"
    assert message_payload["reflection"] == "Captured empowerment metrics."
    assert message_payload["guardrails"]["status"] == "ok"
