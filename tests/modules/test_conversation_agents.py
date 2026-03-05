import sys
import types
from typing import List

import pytest

from domain.commerce.types import Product
from infrastructure.memory.semantic_memory import SemanticMemory
from application.services.conversation.agents import (
    CommerceAgent,
    IntentAgent,
    CapabilityAgent,
    ExplainAgent,
)
from application.services.conversation.commerce_plan_builder import CommercePlanBuilder
from api.composition import default_deps
from application.services.evidence.alignment_service import AlignmentService
from application.services.evidence.intentionality_profiler import build_profile
from application.services.conversation.context_builder import context_for

# Provide lightweight google.genai stubs before importing modules that rely on them.
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
            self, function_declarations: List[FunctionDeclaration] | None = None
        ):
            self.function_declarations = function_declarations or []

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg


def _fake_embed_batch(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        seed = sum(ord(ch) for ch in str(text))
        vectors.append([((seed + i * 31) % 1000) / 1000.0 for i in range(16)])
    return vectors


@pytest.fixture(autouse=True)
def _fast_alignment(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.alignment.goal_alignment_gateway.embeddings_provider.embed_batch",
        _fake_embed_batch,
    )
    monkeypatch.setattr(
        "infrastructure.alignment.goal_alignment_gateway._embedding_provider_name",
        lambda: "stub",
    )


@pytest.fixture
def fake_reasoner():
    def _fake_reasoner(goals, products, context=None):
        annotated = []
        for product in products:
            copy = dict(product)
            copy["reasoning"] = f"Supports {', '.join(goals) or 'autonomy'}"
            annotated.append(copy)
        return annotated

    return _fake_reasoner


def test_commerce_agent_emits_clarifications(fake_reasoner):
    mock_products = [
        Product(
            id="p1",
            name="Focus Chair",
            price=499.0,
            tags=["chair"],
            confidence=0.6,
            source="product",
            merchant_name="Mock Merchant",
            capabilities_enabled=["Improve posture"],
        )
    ]

    builder = CommercePlanBuilder(
        search_fn=lambda query, client_id=None, brand_id=None: mock_products,
        compare_fn=lambda products: {},
        build_profile_fn=build_profile,
    )
    agent = CommerceAgent(
        builder=builder,
        reason_fn=fake_reasoner,
        assess_fn=AlignmentService(default_deps()).assess,
        score_fn=AlignmentService(default_deps()).score_products,
        search_fn=lambda q, client_id=None, brand_id=None: mock_products,
    )
    plan = agent.build_plan(
        {"primary_goal": "workspace"},
        goals=["workspace upgrade"],
        client_id="client-1",
    )
    clarifications = plan["clarifications"]
    assert any("confidence" in message.lower() for message in clarifications)
    assert plan["data_quality"]["average_confidence"] == round(0.6, 2)
    assert "goal_alignment" in plan["alignment"]


def test_commerce_agent_filters_low_confidence(fake_reasoner):
    products = [
        Product(
            id="p_high",
            name="High",
            price=100,
            tags=[],
            confidence=0.95,
            source="product",
            merchant_name="M1",
        ),
        Product(
            id="p_mid",
            name="Mid",
            price=150,
            tags=[],
            confidence=0.7,
            source="product",
            merchant_name="M2",
        ),
        Product(
            id="p_low",
            name="Low",
            price=80,
            tags=[],
            confidence=0.3,
            source="product",
            merchant_name="M3",
        ),
    ]
    builder = CommercePlanBuilder(
        search_fn=lambda query, client_id=None, brand_id=None: products,
        compare_fn=lambda products: {},
        build_profile_fn=build_profile,
    )
    agent = CommerceAgent(
        builder=builder,
        reason_fn=fake_reasoner,
        assess_fn=AlignmentService(default_deps()).assess,
        score_fn=AlignmentService(default_deps()).score_products,
        search_fn=lambda q, client_id=None, brand_id=None: products,
    )
    plan = agent.build_plan(
        {"primary_goal": "workspace"},
        goals=["workspace"],
        client_id="client-1",
    )
    ids = [product["id"] for product in plan["products"]]
    assert ids == ["p_high", "p_mid"]
    assert any("hidden" in message.lower() for message in plan["clarifications"])
    assert plan["alignment"]["goal_alignment"]["score"] >= 0.0


def test_commerce_agent_fallback_query(fake_reasoner):
    def mock_search(query: str, client_id=None, brand_id=None):
        mapping = {
            "workspace upgrade": [],
            "career": [
                Product(
                    id="career1",
                    name="Career Product",
                    price=200,
                    tags=["workspace"],
                    confidence=0.8,
                    source="product",
                    merchant_name="CareerShop",
                )
            ],
        }
        return mapping.get(query, [])

    builder = CommercePlanBuilder(
        search_fn=mock_search,
        compare_fn=lambda products: {},
        build_profile_fn=build_profile,
    )
    agent = CommerceAgent(
        builder=builder,
        reason_fn=fake_reasoner,
        assess_fn=AlignmentService(default_deps()).assess,
        score_fn=AlignmentService(default_deps()).score_products,
        search_fn=mock_search,
    )
    plan = agent.build_plan(
        {"primary_goal": "workspace upgrade", "domain": "career"},
        goals=["career growth"],
        client_id="client-1",
    )
    assert plan["query"] == "career"
    assert any("fell back" in clarification for clarification in plan["clarifications"])


def test_explain_agent_mentions_confidence():
    products = [
        {"name": "Focus Chair", "confidence": 0.6, "source": "product"},
        {"name": "Desk", "confidence": 0.9, "source": "product"},
    ]
    explanation = ExplainAgent().explain(products)
    assert "Focus Chair" in explanation and "0.60" in explanation


def test_intent_agent_routes_through_hybrid(monkeypatch):
    classifier_calls = {"count": 0}

    class FakeResult:
        def to_dict(self):
            classifier_calls["count"] += 1
            return {"primary_goal": "workspace upgrade", "confidence": 0.9}

    class FakeClassifier:
        def classify(self, text, context=None):
            assert context in (None, "")
            return FakeResult()

    intent_agent = IntentAgent(
        classifier=FakeClassifier(),
        context_for_fn=context_for,
        log_replay_fn=None,
    )
    result = intent_agent.detect_intent("Need focus")

    assert result["primary_goal"] == "workspace upgrade"
    assert classifier_calls["count"] == 1


def test_capability_agent_reads_semantic_memory(monkeypatch, tmp_path):
    db_path = tmp_path / "memory.db"
    memory = SemanticMemory(data_path=db_path)
    memory.set("goals", ["Improve posture"])
    memory.set("capabilities", ["Ergo expert"])

    agent = CapabilityAgent(memory_factory=lambda: SemanticMemory(data_path=db_path))
    summary = agent.summarize()

    assert summary["goals"] == ["Improve posture"]
    assert summary["capabilities"] == ["Ergo expert"]
