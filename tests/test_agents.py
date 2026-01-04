from agents.commerce_agent import CommerceAgent
from agents.reflection_agent import ReflectionAgent
from core.schema.product import Product


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
    plan = agent.build_plan({"label": "workspace"})
    clarifications = plan["clarifications"]
    assert any("confidence" in message.lower() for message in clarifications)
    assert plan["data_quality"]["average_confidence"] == round(0.6, 2)


def test_commerce_agent_filters_low_confidence(monkeypatch):
    products = [
        Product(id="p_high", name="High", price=100, tags=[], confidence=0.95, source="shopify", merchant_name="M1"),
        Product(id="p_mid", name="Mid", price=150, tags=[], confidence=0.7, source="google_shopping", merchant_name="M2"),
        Product(id="p_low", name="Low", price=80, tags=[], confidence=0.3, source="google_shopping", merchant_name="M3"),
    ]
    monkeypatch.setattr("src.products.search.search", lambda query: products)
    agent = CommerceAgent()
    plan = agent.build_plan({"label": "workspace"})
    ids = [product["id"] for product in plan["products"]]
    assert ids == ["p_high", "p_mid"]
    assert any("hidden" in message.lower() for message in plan["clarifications"])


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
