from modules.commerce.domain import Product
from modules.intentionality.profiling import build_profile


def test_build_profile_uses_capabilities_and_description():
    product = Product(
        id="p1",
        name="Focus Chair",
        price=199.0,
        tags=["chair"],
        description="Reduce back strain during long sessions. Adjustable lumbar.",
        capabilities_enabled=["Reduce back strain"],
        intent_scores={"posture": 0.9},
    )

    profile = build_profile(product)
    assert profile.capabilities_enabled == ["Reduce back strain"]
    assert "Reduce back strain" in profile.goals_served
    assert profile.outcomes_expected
    assert profile.context_fit["posture"] == 0.9
