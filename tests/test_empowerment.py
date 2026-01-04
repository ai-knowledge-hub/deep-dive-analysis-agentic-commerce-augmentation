from src.empowerment.goal_alignment import assess
from src.products.search import search


def test_goal_alignment_scores_supporting_products():
    products = search("workspace")
    goals = ["Improve posture", "Learn guitar"]
    result = assess(goals, products)
    assert "Improve posture" in result.aligned_goals
    assert "Learn guitar" in result.misaligned_goals
    assert result.score < 1
    assert result.supporting_products
