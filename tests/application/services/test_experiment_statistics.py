"""Unit tests for experiment statistics module."""

import pytest
from application.services.experiment_statistics import (
    compare_variants,
    analyze_trend,
    detect_diminishing_returns,
)


def test_compare_variants_significant_difference():
    """Test statistical comparison with significant difference."""
    variant_a = {
        "id": "baseline",
        "metrics": {"win_rate": 0.40, "total_runs": 100, "wins": 40},
    }
    variant_b = {
        "id": "hypothesis",
        "metrics": {"win_rate": 0.60, "total_runs": 100, "wins": 60},
    }

    result = compare_variants(variant_a, variant_b, metric_name="win_rate")

    assert result.variant_a_id == "baseline"
    assert result.variant_b_id == "hypothesis"
    assert result.difference == pytest.approx(0.20, abs=0.01)
    assert result.is_significant is True
    assert result.evidence_strength in {"moderate", "strong"}
    # Cohen's h for 0.4 -> 0.6 is ~0.40
    assert abs(result.effect_size) > 0.3
    assert len(result.confidence_interval) == 2


def test_compare_variants_no_significant_difference():
    """Test statistical comparison with no significant difference."""
    variant_a = {
        "id": "baseline",
        "metrics": {"win_rate": 0.50, "total_runs": 10, "wins": 5},
    }
    variant_b = {
        "id": "hypothesis",
        "metrics": {"win_rate": 0.55, "total_runs": 10, "wins": 6},
    }

    result = compare_variants(variant_a, variant_b, metric_name="win_rate")

    assert result.difference == pytest.approx(0.05, abs=0.01)
    assert result.is_significant is False
    assert result.evidence_strength == "weak"


def test_compare_variants_small_effect_size():
    """Test statistical comparison with small effect size."""
    variant_a = {
        "id": "baseline",
        "metrics": {"win_rate": 0.48, "total_runs": 100, "wins": 48},
    }
    variant_b = {
        "id": "hypothesis",
        "metrics": {"win_rate": 0.52, "total_runs": 100, "wins": 52},
    }

    result = compare_variants(variant_a, variant_b, metric_name="win_rate")

    assert result.difference == pytest.approx(0.04, abs=0.01)
    assert abs(result.effect_size) < 0.2  # Small effect


def test_analyze_trend_improving():
    """Test trend analysis with improving performance."""
    metrics_history = [
        {"variant_id": "v1", "metrics": {"win_rate": 0.40}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.45}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.50}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.55}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.60}},
    ]

    result = analyze_trend("v1", metrics_history, metric_name="win_rate")

    assert result.variant_id == "v1"
    assert result.trend_direction == "improving"
    assert result.slope > 0
    assert result.r_squared > 0.9  # Strong linear fit


def test_analyze_trend_declining():
    """Test trend analysis with declining performance."""
    metrics_history = [
        {"variant_id": "v1", "metrics": {"win_rate": 0.60}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.55}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.50}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.45}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.40}},
    ]

    result = analyze_trend("v1", metrics_history, metric_name="win_rate")

    assert result.trend_direction == "declining"
    assert result.slope < 0


def test_analyze_trend_stable():
    """Test trend analysis with stable performance."""
    metrics_history = [
        {"variant_id": "v1", "metrics": {"win_rate": 0.50}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.51}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.49}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.50}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.50}},
    ]

    result = analyze_trend("v1", metrics_history, metric_name="win_rate")

    assert result.trend_direction == "stable"
    assert abs(result.slope) < 0.01


def test_analyze_trend_volatile():
    """Test trend analysis with volatile performance."""
    metrics_history = [
        {"variant_id": "v1", "metrics": {"win_rate": 0.30}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.70}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.40}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.65}},
        {"variant_id": "v1", "metrics": {"win_rate": 0.35}},
    ]

    result = analyze_trend("v1", metrics_history, metric_name="win_rate")

    assert result.trend_direction == "volatile"
    assert result.volatility > 0.3


def test_analyze_trend_insufficient_data():
    """Test trend analysis with insufficient data."""
    metrics_history = [
        {"variant_id": "v1", "metrics": {"win_rate": 0.50}},
    ]

    result = analyze_trend("v1", metrics_history, metric_name="win_rate")

    assert result.trend_direction == "insufficient_data"
    assert result.confidence == 0.0


def test_detect_diminishing_returns_true():
    """Test diminishing returns detection when true."""
    metrics_history = [
        {"metrics": {"win_rate": 0.40}},
        {"metrics": {"win_rate": 0.50}},
        {"metrics": {"win_rate": 0.55}},
        {"metrics": {"win_rate": 0.56}},
        {"metrics": {"win_rate": 0.565}},
    ]

    result = detect_diminishing_returns(metrics_history, threshold=0.02)

    assert result is True


def test_detect_diminishing_returns_false():
    """Test diminishing returns detection when false."""
    metrics_history = [
        {"metrics": {"win_rate": 0.40}},
        {"metrics": {"win_rate": 0.45}},
        {"metrics": {"win_rate": 0.50}},
        {"metrics": {"win_rate": 0.55}},
        {"metrics": {"win_rate": 0.60}},
    ]

    result = detect_diminishing_returns(metrics_history, threshold=0.02)

    assert result is False


def test_detect_diminishing_returns_insufficient_data():
    """Test diminishing returns with insufficient data."""
    metrics_history = [
        {"metrics": {"win_rate": 0.40}},
        {"metrics": {"win_rate": 0.50}},
    ]

    result = detect_diminishing_returns(metrics_history, threshold=0.02)

    assert result is False


def test_compare_variants_edge_case_zero_variance():
    """Test comparison when both variants have same performance."""
    variant_a = {
        "id": "baseline",
        "metrics": {"win_rate": 0.50, "total_runs": 100, "wins": 50},
    }
    variant_b = {
        "id": "hypothesis",
        "metrics": {"win_rate": 0.50, "total_runs": 100, "wins": 50},
    }

    result = compare_variants(variant_a, variant_b, metric_name="win_rate")

    assert result.difference == pytest.approx(0.0, abs=0.001)
    assert result.is_significant is False


def test_compare_variants_avg_score_metric():
    """Test comparison using avg_score instead of win_rate."""
    variant_a = {
        "id": "baseline",
        "metrics": {"avg_score": 0.60, "total_runs": 50},
    }
    variant_b = {
        "id": "hypothesis",
        "metrics": {"avg_score": 0.75, "total_runs": 50},
    }

    result = compare_variants(variant_a, variant_b, metric_name="avg_score")

    assert result.metric_name == "avg_score"
    assert result.difference == pytest.approx(0.15, abs=0.01)


def test_effect_size_interpretation():
    """Test effect size boundaries for interpretation."""
    # Small effect (< 0.2) for Cohen's h
    variant_a = {"id": "a", "metrics": {"win_rate": 0.48, "total_runs": 100}}
    variant_b = {"id": "b", "metrics": {"win_rate": 0.52, "total_runs": 100}}
    result_small = compare_variants(variant_a, variant_b)
    assert abs(result_small.effect_size) < 0.2

    # Medium effect (0.2 <= h < 0.5)
    variant_a = {"id": "a", "metrics": {"win_rate": 0.40, "total_runs": 100}}
    variant_b = {"id": "b", "metrics": {"win_rate": 0.55, "total_runs": 100}}
    result_medium = compare_variants(variant_a, variant_b)
    assert 0.2 <= abs(result_medium.effect_size) < 0.5

    # Large effect (>= 0.5)
    variant_a = {"id": "a", "metrics": {"win_rate": 0.30, "total_runs": 100}}
    variant_b = {"id": "b", "metrics": {"win_rate": 0.60, "total_runs": 100}}
    result_large = compare_variants(variant_a, variant_b)
    assert abs(result_large.effect_size) >= 0.5


def test_confidence_interval_contains_zero():
    """Test that non-significant results have CI containing zero."""
    variant_a = {
        "id": "baseline",
        "metrics": {"win_rate": 0.50, "total_runs": 20, "wins": 10},
    }
    variant_b = {
        "id": "hypothesis",
        "metrics": {"win_rate": 0.52, "total_runs": 20, "wins": 11},
    }

    result = compare_variants(variant_a, variant_b)

    # Non-significant result should have CI containing zero
    if not result.is_significant:
        ci_lower, ci_upper = result.confidence_interval
        assert ci_lower < 0 < ci_upper
