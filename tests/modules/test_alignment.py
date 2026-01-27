from domain.commerce.search import search
from infrastructure.alignment.goal_alignment_gateway import assess
from infrastructure.commerce.demo_catalog import load_demo_catalog


def test_goal_alignment_scores_supporting_products():
    catalog = load_demo_catalog()
    products = search(catalog, "workspace")
    goals = ["Improve posture", "Learn guitar"]
    result = assess(goals, products, use_semantic=False)
    assert "Improve posture" in result.aligned_goals
    assert "Learn guitar" in result.misaligned_goals
    assert result.score < 1
    assert result.supporting_products
    assert "average_confidence" in result.confidence_summary
    avg_conf = result.confidence_summary["average_confidence"]
    assert isinstance(avg_conf, (int, float))
    assert avg_conf >= 0
