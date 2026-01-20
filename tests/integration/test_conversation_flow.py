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

from modules.values.domain import GoalClarificationState
from db.connection import set_database_path, init_db
from api.main import app


@pytest.fixture()
def integration_client(tmp_path, monkeypatch):
    db_path = tmp_path / "integration.db"
    set_database_path(db_path)
    init_db()

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
            return {
                "query": "workspace focus kit",
                "products": [
                    {
                        "id": "p1",
                        "name": "Focus Chair",
                        "capabilities_enabled": ["Posture"],
                        "confidence": 0.8,
                        "source": "mock",
                        "reasoning": f"Supports {goals[0]}"
                        if goals
                        else "Supports focus",
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

    return TestClient(app)


def test_full_conversation_flow(integration_client):
    start_response = integration_client.post(
        "/conversation/start",
        json={"opening_message": "Need focus", "user_id": "integration-user"},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    session_id = start_payload["session_id"]
    assert (
        start_payload["plan"]["products"][0]["reasoning"] == "Supports Stay energized"
    )
    assert start_payload["intentionality_profiles"]

    message_response = integration_client.post(
        f"/conversation/{session_id}/message",
        json={"message": "continue", "user_id": "integration-user"},
    )
    assert message_response.status_code == 200
    message_payload = message_response.json()

    assert message_payload["intent"]["primary_goal"] == "workspace upgrade"
    assert (
        message_payload["plan"]["products"][0]["reasoning"] == "Supports Stay energized"
    )
