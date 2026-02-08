"""Unit tests for experiment ML engine."""

import pytest
from application.services.experiment.ml import ExperimentMLEngine, ExperimentFeatures


def test_ml_engine_fallback_recommendation():
    """Test ML engine fallback when no historical data."""
    engine = ExperimentMLEngine()

    product = {
        "id": "product_1",
        "name": "Samsung QLED 65-inch",
        "description": "4K QLED display with 3000 nits peak brightness, Quantum Processor 4K, 120Hz refresh rate",
    }
    experiment = {"id": "exp_1", "product_id": "product_1"}
    beliefs = []

    recommendation = engine.predict_best_hypothesis(experiment, product, beliefs)

    assert recommendation is not None
    assert recommendation.hypothesis_type == "copy"
    assert 0.0 <= recommendation.confidence <= 1.0
    assert len(recommendation.rationale) > 0


def test_ml_engine_has_outcome_language():
    """Test detection of outcome-focused language."""
    engine = ExperimentMLEngine()

    # Has outcome language
    description_with_outcome = (
        "Combat glare in bright rooms with anti-reflective coating"
    )
    assert engine._has_outcome_language(description_with_outcome) is True

    # No outcome language
    description_without_outcome = "4K display 3000 nits 120Hz refresh rate"
    assert engine._has_outcome_language(description_without_outcome) is False


def test_ml_engine_has_technical_specs():
    """Test detection of technical specifications."""
    engine = ExperimentMLEngine()

    # Has technical specs
    description_with_specs = "65-inch 4K QLED 3000 nits 120Hz"
    assert engine._has_technical_specs(description_with_specs) is True

    # No technical specs
    description_without_specs = "Beautiful large TV for your living room"
    assert engine._has_technical_specs(description_without_specs) is False


def test_ml_engine_calculate_complexity():
    """Test product complexity calculation."""
    engine = ExperimentMLEngine()

    # Simple description
    simple = "Beautiful TV"
    complexity_simple = engine._calculate_complexity(simple)
    assert 0.0 <= complexity_simple <= 0.3

    # Complex description with specs
    complex = "65-inch 4K QLED 3000 nits 120Hz Quantum Processor 4K"
    complexity_complex = engine._calculate_complexity(complex)
    assert complexity_complex > complexity_simple


def test_ml_engine_infer_product_type():
    """Test product type inference."""
    engine = ExperimentMLEngine()

    # Electronics display
    tv_desc = "65-inch TV with 4K display"
    assert engine._infer_product_type(tv_desc) == "electronics_display"

    # Footwear
    shoe_desc = "Running sneakers with cushioning"
    assert engine._infer_product_type(shoe_desc) == "footwear"

    # Apparel
    jacket_desc = "Winter jacket with insulation"
    assert engine._infer_product_type(jacket_desc) == "apparel"

    # General
    other_desc = "Kitchen utensil set"
    assert engine._infer_product_type(other_desc) == "general"


def test_ml_engine_compute_similarity():
    """Test similarity computation between experiments."""
    engine = ExperimentMLEngine()

    current = {
        "product_type": "electronics_display",
        "product_complexity": 0.6,
        "has_technical_specs": True,
        "has_outcome_language": False,
        "baseline_win_rate": 0.40,
    }

    # Very similar past experiment
    past_similar = ExperimentFeatures(
        product_type="electronics_display",
        product_complexity=0.65,
        has_technical_specs=True,
        has_outcome_language=False,
        baseline_win_rate=0.42,
        baseline_avg_score=0.5,
        num_competitors=3,
        intervention_type="copy",
        changed_outcome_framing=False,
        changed_technical_detail=False,
        changed_tone=False,
        win_rate_lift=0.15,
        avg_score_lift=0.1,
        protocol_readiness_delta=0.0,
    )

    similarity_high = engine._compute_similarity(current, past_similar)
    assert similarity_high > 0.7

    # Dissimilar past experiment
    past_dissimilar = ExperimentFeatures(
        product_type="footwear",
        product_complexity=0.2,
        has_technical_specs=False,
        has_outcome_language=True,
        baseline_win_rate=0.70,
        baseline_avg_score=0.8,
        num_competitors=5,
        intervention_type="tone",
        changed_outcome_framing=True,
        changed_technical_detail=False,
        changed_tone=True,
        win_rate_lift=0.05,
        avg_score_lift=0.03,
        protocol_readiness_delta=0.0,
    )

    similarity_low = engine._compute_similarity(current, past_dissimilar)
    assert similarity_low < similarity_high


def test_ml_engine_with_training_data():
    """Test ML engine with historical training data."""
    engine = ExperimentMLEngine()

    # Create mock historical experiments
    historical = [
        {
            "id": "exp_1",
            "product": {
                "description": "4K TV with 3000 nits brightness and 120Hz refresh",
            },
            "variants": [
                {
                    "id": "v1",
                    "payload": {"description": "4K TV with 3000 nits and 120Hz"},
                    "metrics": {"win_rate": 0.40, "avg_score": 0.5},
                },
                {
                    "id": "v2",
                    "type": "copy",
                    "payload": {
                        "description": "Combat glare in bright rooms with 3000-nit peak brightness. Smooth 120Hz gaming."
                    },
                    "metrics": {"win_rate": 0.60, "avg_score": 0.7},
                },
            ],
        },
    ]

    engine.fit(historical)

    # Now predict for similar product
    product = {"description": "55-inch 4K TV with 2500 nits brightness and 120Hz"}
    experiment = {"id": "exp_new", "product_id": "prod_new"}

    recommendation = engine.predict_best_hypothesis(experiment, product, [])

    assert recommendation.hypothesis_type == "copy"
    assert recommendation.confidence > 0.3
    assert recommendation.predicted_lift > 0.0


def test_ml_engine_brand_belief_integration():
    """Test integration of brand beliefs into recommendations."""
    engine = ExperimentMLEngine()

    product = {"description": "4K TV with 3000 nits brightness"}
    experiment = {"id": "exp_1"}
    beliefs = [
        {
            "id": "belief_1",
            "recommendation": "Outcome framing improves glare-intent queries by 63%",
            "confidence": 0.82,
            "metadata": {"variant_type": "copy"},
        }
    ]

    recommendation = engine.predict_best_hypothesis(experiment, product, beliefs)

    # Should mention the brand belief in rationale
    assert (
        "belief" in recommendation.rationale.lower()
        or "brand" in recommendation.rationale.lower()
    )


def test_ml_engine_suggest_outcome_framing():
    """Test outcome framing suggestion."""
    engine = ExperimentMLEngine()

    description = "4K TV with 3000 nits brightness"
    suggestion = engine._suggest_outcome_framing(description)

    assert len(suggestion) > len(description)
    assert description in suggestion


def test_ml_engine_extract_belief_insights():
    """Test extraction of relevant belief insights."""
    engine = ExperimentMLEngine()

    beliefs = [
        {
            "recommendation": "Outcome framing works for glare queries",
            "confidence": 0.8,
            "metadata": {"variant_type": "copy"},
        },
        {
            "recommendation": "Technical detail reduction helps",
            "confidence": 0.6,
            "metadata": {"variant_type": "protocol"},
        },
    ]

    # Should extract copy-related belief
    insight_copy = engine._extract_belief_insights(beliefs, "copy")
    assert "outcome framing" in insight_copy.lower() or len(insight_copy) > 0

    # Should not extract unrelated belief
    insight_tone = engine._extract_belief_insights(beliefs, "tone")
    assert len(insight_tone) == 0 or "belief" not in insight_tone.lower()


def test_ml_engine_features_to_dict():
    """Test feature conversion to dictionary."""
    engine = ExperimentMLEngine()

    features = ExperimentFeatures(
        product_type="electronics_display",
        product_complexity=0.6,
        has_technical_specs=True,
        has_outcome_language=False,
        baseline_win_rate=0.40,
        baseline_avg_score=0.5,
        num_competitors=3,
        intervention_type="copy",
        changed_outcome_framing=True,
        changed_technical_detail=False,
        changed_tone=False,
        win_rate_lift=0.15,
        avg_score_lift=0.1,
        protocol_readiness_delta=0.0,
    )

    feature_dict = engine._features_to_dict(features)

    assert feature_dict["product_type"] == "electronics_display"
    assert feature_dict["product_complexity"] == 0.6
    assert feature_dict["has_technical_specs"] is True
    assert feature_dict["win_rate_lift"] == 0.15


def test_ml_engine_detect_outcome_framing_change():
    """Test detection of outcome framing change."""
    engine = ExperimentMLEngine()

    baseline = {"payload": {"description": "4K TV with 3000 nits"}}
    variant = {"payload": {"description": "Combat glare with 3000-nit brightness"}}

    changed = engine._detect_outcome_framing_change(baseline, variant)
    assert changed is True

    # No change
    baseline_with_outcome = {
        "payload": {"description": "Combat glare with 3000-nit brightness"}
    }
    variant_same = {"payload": {"description": "Reduce glare with 3000-nit brightness"}}
    changed_false = engine._detect_outcome_framing_change(
        baseline_with_outcome, variant_same
    )
    assert changed_false is False


def test_ml_engine_predict_lift():
    """Test lift prediction from similar experiments."""
    engine = ExperimentMLEngine()

    similar = [
        ({"intervention_type": "copy", "win_rate_lift": 0.15}, 0.9),
        ({"intervention_type": "copy", "win_rate_lift": 0.12}, 0.8),
        ({"intervention_type": "copy", "win_rate_lift": 0.18}, 0.85),
        ({"intervention_type": "tone", "win_rate_lift": 0.05}, 0.7),
    ]

    predicted_lift = engine._predict_lift(similar, "copy")

    # Should average the copy interventions (0.15 + 0.12 + 0.18) / 3
    assert predicted_lift == pytest.approx(0.15, abs=0.01)


def test_ml_engine_calculate_confidence():
    """Test confidence calculation."""
    engine = ExperimentMLEngine()

    # High confidence scenario: many similar experiments with high similarity and lift
    similar_many = [
        ({"intervention_type": "copy", "win_rate_lift": 0.15}, 0.9),
        ({"intervention_type": "copy", "win_rate_lift": 0.12}, 0.85),
        ({"intervention_type": "copy", "win_rate_lift": 0.18}, 0.88),
        ({"intervention_type": "copy", "win_rate_lift": 0.16}, 0.87),
        ({"intervention_type": "copy", "win_rate_lift": 0.14}, 0.86),
    ]

    confidence_high = engine._calculate_confidence(similar_many, "copy")
    assert confidence_high > 0.6

    # Low confidence scenario: few experiments
    similar_few = [
        ({"intervention_type": "copy", "win_rate_lift": 0.05}, 0.5),
    ]

    confidence_low = engine._calculate_confidence(similar_few, "copy")
    assert confidence_low < confidence_high
