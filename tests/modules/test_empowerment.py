from modules.empowerment.goal_alignment import assess
from modules.commerce import search


def test_goal_alignment_scores_supporting_products():
    products = search("workspace")
    goals = ["Improve posture", "Learn guitar"]
    result = assess(goals, products)
    assert "Improve posture" in result.aligned_goals
    assert "Learn guitar" in result.misaligned_goals
    assert result.score < 1
    assert result.supporting_products
    assert "average_confidence" in result.confidence_summary
    avg_conf = result.confidence_summary["average_confidence"]
    assert isinstance(avg_conf, (int, float))
    assert avg_conf >= 0
