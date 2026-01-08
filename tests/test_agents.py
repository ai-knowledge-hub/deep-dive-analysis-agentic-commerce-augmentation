import sys
import types
from typing import List

import pytest

from core.schema.product import Product
from src.memory.semantic import SemanticMemory
from orchestration.commerce_service import CommerceAgent
from orchestration.reflection_service import ReflectionAgent

# Provide lightweight google.genai stubs before importing modules that rely on them.
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
        def __init__(self, function_declarations: List[FunctionDeclaration] | None = None):
            self.function_declarations = function_declarations or []

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
sys.modules["google"] = google_pkg
sys.modules["google.genai"] = genai_pkg
sys.modules["google.genai.types"] = genai_types_pkg

from orchestration.intent_service import IntentAgent
from orchestration.capability_service import CapabilityAgent


@pytest.fixture(autouse=True)
def mock_reason_about_products(monkeypatch):
    def _fake_reasoner(goals, products):
        annotated = []
        for product in products:
            copy = dict(product)
            copy["reasoning"] = f"Supports {', '.join(goals) or 'autonomy'}"
            annotated.append(copy)
        return annotated

    monkeypatch.setattr("orchestration.commerce_service.reason_about_products", _fake_reasoner)
    yield


def test_commerce_agent_emits_clarifications(monkeypatch):
    mock_products = [
        Product(
            id="p1",
            name="Focus Chair",
            price=499.0,
            tags=["chair"],
            confidence=0.6,
            source="google_shopping",
            merchant_name="Mock Merchant",
            capabilities_enabled=["Improve posture"],
        )
    ]

    monkeypatch.setattr("src.products.search.search", lambda query: mock_products)
    agent = CommerceAgent()
    plan = agent.build_plan({"label": "workspace"}, goals=["workspace upgrade"])
    clarifications = plan["clarifications"]
    assert any("confidence" in message.lower() for message in clarifications)
    assert plan["data_quality"]["average_confidence"] == round(0.6, 2)
    assert "goal_alignment" in plan["empowerment"]


def test_commerce_agent_filters_low_confidence(monkeypatch):
    products = [
        Product(id="p_high", name="High", price=100, tags=[], confidence=0.95, source="shopify", merchant_name="M1"),
        Product(id="p_mid", name="Mid", price=150, tags=[], confidence=0.7, source="google_shopping", merchant_name="M2"),
        Product(id="p_low", name="Low", price=80, tags=[], confidence=0.3, source="google_shopping", merchant_name="M3"),
    ]
    monkeypatch.setattr("src.products.search.search", lambda query: products)
    agent = CommerceAgent()
    plan = agent.build_plan({"label": "workspace"}, goals=["workspace"])
    ids = [product["id"] for product in plan["products"]]
    assert ids == ["p_high", "p_mid"]
    assert any("hidden" in message.lower() for message in plan["clarifications"])
    assert plan["empowerment"]["goal_alignment"]["score"] >= 0.0

def test_commerce_agent_fallback_query(monkeypatch):
    def mock_search(query: str):
        mapping = {
            "workspace upgrade": [],
            "career": [
                Product(
                    id="career1",
                    name="Career Product",
                    price=200,
                    tags=["workspace"],
                    confidence=0.8,
                    source="google_shopping",
                    merchant_name="CareerShop",
                )
            ],
        }
        return mapping.get(query, [])

    monkeypatch.setattr("src.products.search.search", mock_search)
    agent = CommerceAgent()
    plan = agent.build_plan({"label": "workspace_upgrade", "domain": "career"}, goals=["career growth"])
    assert plan["query"] == "career"
    assert any("fell back" in clarification for clarification in plan["clarifications"])


def test_reflection_mentions_data_quality():
    plan = {
        "query": "workspace",
        "products": [{"id": "p1"}],
        "data_quality": {"average_confidence": 0.58},
        "clarifications": ["Data confidence is low; request merchant-verified options or additional context."],
    }
    agent = ReflectionAgent()
    reflection_text = agent.reflect(plan)
    assert "Average data confidence" in reflection_text
    assert "Clarification" in reflection_text
from orchestration.autonomy_guard_service import AutonomyGuardAgent
from orchestration.explain_service import ExplainAgent


def test_explain_agent_mentions_confidence():
    products = [
        {"name": "Focus Chair", "confidence": 0.6, "source": "google_shopping"},
        {"name": "Desk", "confidence": 0.9, "source": "shopify"},
    ]
    explanation = ExplainAgent().explain(products)
    assert "Focus Chair" in explanation and "0.60" in explanation


def test_autonomy_guard_flags_low_confidence():
    guard = AutonomyGuardAgent()
    result = guard.check(
        rationale="",
        clarifications=["Some recommendations come from discovery"],
        products=[{"confidence": 0.4, "source": "google_shopping"}],
    )
    assert result["status"] == "needs_review"
    assert any("confidence" in flag.lower() for flag in result["flags"])


def test_intent_agent_routes_through_hybrid(monkeypatch):
    classifier_calls = {"count": 0}

    class FakeResult:
        def to_dict(self):
            classifier_calls["count"] += 1
            return {"label": "workspace_upgrade", "confidence": 0.9}

    monkeypatch.setattr(
        "orchestration.intent_service.HybridIntentClassifier",
        lambda: type("Fake", (), {"classify": lambda self, _: FakeResult()})(),
    )

    intent_agent = IntentAgent()
    result = intent_agent.detect_intent("Need focus")

    assert result["label"] == "workspace_upgrade"
    assert classifier_calls["count"] == 1


def test_capability_agent_reads_semantic_memory(monkeypatch, tmp_path):
    db_path = tmp_path / "memory.db"
    memory = SemanticMemory(data_path=db_path)
    memory.set("goals", ["Improve posture"])
    memory.set("capabilities", ["Ergo expert"])

    monkeypatch.setattr("orchestration.capability_service.SemanticMemory", lambda: SemanticMemory(data_path=db_path))

    agent = CapabilityAgent()
    summary = agent.summarize()

    assert summary["goals"] == ["Improve posture"]
    assert summary["capabilities"] == ["Ergo expert"]
