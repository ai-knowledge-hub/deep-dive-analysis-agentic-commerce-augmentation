from domain.commerce.search import search
from domain.commerce.types import Product
from infrastructure.alignment.goal_alignment_gateway import assess


def test_goal_alignment_scores_supporting_products():
    products = [
        Product(
            id="chair-1",
            name="Posture Support Chair",
            description="Ergonomic chair for better posture.",
            price=299.0,
            tags=["ergonomic", "workspace"],
            capabilities_enabled=["Improve posture"],
            confidence=0.9,
            source="product",
        ),
        Product(
            id="guitar-1",
            name="Acoustic Guitar",
            description="Entry-level acoustic guitar for beginners.",
            price=199.0,
            tags=["music"],
            capabilities_enabled=["Learn guitar"],
            confidence=0.7,
            source="product",
        ),
    ]
    results = search(products, "workspace")
    goals = ["Improve posture", "Learn guitar"]
    result = assess(goals, results, use_semantic=False)
    assert "Improve posture" in result.aligned_goals
    assert "Learn guitar" in result.misaligned_goals
    assert result.score < 1
    assert result.supporting_products
    assert "average_confidence" in result.confidence_summary
    avg_conf = result.confidence_summary["average_confidence"]
    assert isinstance(avg_conf, (int, float))
    assert avg_conf >= 0
