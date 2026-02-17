from application.services.experiment.decision_policy import (
    DecisionInputs,
    EvidenceSignal,
    decide,
)


def test_decision_policy_promotes_on_strong_positive_experiment_signal() -> None:
    inputs = DecisionInputs(
        exp=EvidenceSignal(effect=1.0, reliability=1.0, support_size=20),
        syn=EvidenceSignal(effect=None, reliability=0.0),
        obs=EvidenceSignal(effect=None, reliability=0.0),
        coverage_obs=0.0,
    )
    out = decide(inputs)
    assert out.action == "promote_variant"
    assert out.promotion_tier == "lab"


def test_decision_policy_iterates_on_moderate_signal() -> None:
    inputs = DecisionInputs(
        exp=EvidenceSignal(effect=0.4, reliability=1.0, support_size=20),
        syn=EvidenceSignal(effect=None, reliability=0.0),
        obs=EvidenceSignal(effect=None, reliability=0.0),
        coverage_obs=0.0,
    )
    out = decide(inputs)
    assert out.action == "iterate_variant"


def test_decision_policy_observed_weight_increases_with_coverage() -> None:
    low = decide(
        DecisionInputs(
            exp=EvidenceSignal(effect=0.0, reliability=1.0),
            syn=EvidenceSignal(effect=0.0, reliability=1.0),
            obs=EvidenceSignal(effect=0.0, reliability=1.0),
            coverage_obs=0.0,
        )
    )
    high = decide(
        DecisionInputs(
            exp=EvidenceSignal(effect=0.0, reliability=1.0),
            syn=EvidenceSignal(effect=0.0, reliability=1.0),
            obs=EvidenceSignal(effect=0.0, reliability=1.0),
            coverage_obs=1.0,
        )
    )
    assert high.weights["obs"] > low.weights["obs"]


def test_decision_policy_prod_tier_requires_min_observed_coverage() -> None:
    inputs = DecisionInputs(
        exp=EvidenceSignal(effect=1.0, reliability=1.0),
        syn=EvidenceSignal(effect=None, reliability=0.0),
        obs=EvidenceSignal(effect=None, reliability=0.0),
        coverage_obs=0.25,
    )
    out = decide(inputs)
    assert out.action == "promote_variant"
    assert out.promotion_tier == "prod"


def test_decision_policy_can_promote_with_strong_synthetic_signal_when_weighted() -> (
    None
):
    # This doesn't assert the exact threshold math, just that synthetic contributes.
    inputs = DecisionInputs(
        exp=EvidenceSignal(effect=0.0, reliability=1.0),
        syn=EvidenceSignal(effect=1.0, reliability=1.0, support_size=10),
        obs=EvidenceSignal(effect=None, reliability=0.0),
        coverage_obs=0.0,
    )
    out = decide(inputs)
    assert out.likelihood > 0.5
