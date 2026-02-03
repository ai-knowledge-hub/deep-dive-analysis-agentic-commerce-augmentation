"""Statistical analysis for experiment results.

Provides hypothesis testing, confidence intervals, effect size calculation,
and trend detection for experiment metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class StatisticalResult:
    """Statistical comparison between two variants."""

    variant_a_id: str
    variant_b_id: str
    metric_name: str
    variant_a_mean: float
    variant_b_mean: float
    variant_a_n: int
    variant_b_n: int
    difference: float
    effect_size: float  # Cohen's h (proportions) / Cohen's d (continuous)
    confidence_interval: Tuple[float, float]  # 95% CI
    p_value: Optional[float]
    is_significant: bool  # derived from CI (avoid over-precision)
    recommended_action: str
    evidence_strength: str  # "weak" | "moderate" | "strong"


@dataclass(frozen=True)
class TrendAnalysis:
    """Trend detection for a variant over time."""

    variant_id: str
    metric_name: str
    values: List[float]
    trend_direction: str  # "improving", "declining", "stable", "volatile"
    slope: float  # linear regression slope
    r_squared: float  # goodness of fit
    volatility: float  # coefficient of variation
    confidence: float  # 0-1


def compare_variants(
    variant_a: Dict[str, Any],
    variant_b: Dict[str, Any],
    metric_name: str = "win_rate",
) -> StatisticalResult:
    """Compare two variants with conservative uncertainty.

    For `win_rate`, prefer proportion intervals and effect sizes over parametric
    tests. LLM/embedding-driven evaluations are noisy; avoid presenting
    pseudo-precise p-values by default.
    """
    a_metrics = variant_a.get("metrics") or {}
    b_metrics = variant_b.get("metrics") or {}

    a_mean = float(a_metrics.get(metric_name) or 0.0)
    b_mean = float(b_metrics.get(metric_name) or 0.0)
    a_n = int(a_metrics.get("total_runs") or 1)
    b_n = int(b_metrics.get("total_runs") or 1)

    if metric_name == "win_rate":
        a_wins = _extract_wins(a_metrics, a_mean, a_n)
        b_wins = _extract_wins(b_metrics, b_mean, b_n)

        a_ci = _wilson_interval(a_wins, a_n)
        b_ci = _wilson_interval(b_wins, b_n)

        difference = b_mean - a_mean
        # Newcombe diff CI using Wilson intervals.
        ci = (b_ci[0] - a_ci[1], b_ci[1] - a_ci[0])
        ci = (max(-1.0, ci[0]), min(1.0, ci[1]))

        is_significant = ci[0] > 0 or ci[1] < 0

        # Cohen's h (proportions): 0.2 small, 0.5 medium, 0.8 large
        effect_size = _cohen_h(a_mean, b_mean)
        evidence_strength = _evidence_strength(
            is_significant=is_significant,
            total_n=a_n + b_n,
            effect_size=abs(effect_size),
        )

        if not is_significant:
            if a_n + b_n < 50:
                action = "Weak evidence—collect more runs before deciding."
            else:
                action = "No clear winner—try a new hypothesis or improve the query battery."
        elif difference > 0:
            action = f"Variant B outperforms A (Δ win rate {abs(difference):.3f}). Deploy B."
        else:
            action = f"Variant A outperforms B (Δ win rate {abs(difference):.3f}). Stick with A."

        return StatisticalResult(
            variant_a_id=variant_a.get("id") or "A",
            variant_b_id=variant_b.get("id") or "B",
            metric_name=metric_name,
            variant_a_mean=a_mean,
            variant_b_mean=b_mean,
            variant_a_n=a_n,
            variant_b_n=b_n,
            difference=difference,
            effect_size=effect_size,
            confidence_interval=ci,
            p_value=None,
            is_significant=is_significant,
            recommended_action=action,
            evidence_strength=evidence_strength,
        )
    else:
        # Conservative estimate: assume std = 0.2 * mean for continuous metrics
        a_se_var = (
            ((0.2 * a_mean) ** 2) / max(a_n, 1) if a_mean > 0 else 0.01 / max(a_n, 1)
        )
        b_se_var = (
            ((0.2 * b_mean) ** 2) / max(b_n, 1) if b_mean > 0 else 0.01 / max(b_n, 1)
        )
        # Population variance
        a_pop_var = ((0.2 * a_mean) ** 2) if a_mean > 0 else 0.01
        b_pop_var = ((0.2 * b_mean) ** 2) if b_mean > 0 else 0.01

    difference = b_mean - a_mean

    # Effect size (Cohen's d) - uses population variance
    pooled_std = math.sqrt(
        (a_pop_var * (a_n - 1) + b_pop_var * (b_n - 1)) / max(a_n + b_n - 2, 1)
    )
    effect_size = difference / pooled_std if pooled_std > 0 else 0.0

    # Welch's t-test - uses standard error variance
    se_diff = math.sqrt(a_se_var + b_se_var)
    t_stat = difference / se_diff if se_diff > 0 else 0.0

    # Degrees of freedom (Welch-Satterthwaite)
    if a_se_var > 0 and b_se_var > 0:
        df = ((a_se_var + b_se_var) ** 2) / (
            (a_se_var**2) / max(a_n - 1, 1) + (b_se_var**2) / max(b_n - 1, 1)
        )
    else:
        df = max(a_n + b_n - 2, 1)

    # 95% CI for difference
    t_critical = 1.96  # approximate for large df
    margin = t_critical * se_diff
    ci = (difference - margin, difference + margin)

    is_significant = ci[0] > 0 or ci[1] < 0
    evidence_strength = _evidence_strength(
        is_significant=is_significant,
        total_n=a_n + b_n,
        effect_size=abs(effect_size),
    )

    # Recommended action
    if not is_significant:
        if a_n + b_n < 20:
            action = "Collect more data—sample size too small for confidence."
        else:
            action = "No clear difference detected. Consider new hypothesis."
    elif effect_size < 0.2:
        action = "Significant but small effect. Consider practical significance."
    elif difference > 0:
        action = f"Variant B outperforms A ({abs(difference):.3f} lift). Deploy B."
    else:
        action = f"Variant A outperforms B ({abs(difference):.3f} lift). Stick with A."

    return StatisticalResult(
        variant_a_id=variant_a.get("id") or "A",
        variant_b_id=variant_b.get("id") or "B",
        metric_name=metric_name,
        variant_a_mean=a_mean,
        variant_b_mean=b_mean,
        variant_a_n=a_n,
        variant_b_n=b_n,
        difference=difference,
        effect_size=effect_size,
        confidence_interval=ci,
        p_value=None,
        is_significant=is_significant,
        recommended_action=action,
        evidence_strength=evidence_strength,
    )


def _extract_wins(metrics: Dict[str, Any], win_rate: float, n: int) -> int:
    wins = metrics.get("wins")
    try:
        if wins is not None:
            return int(wins)
    except (TypeError, ValueError):
        pass
    return int(round(max(0.0, min(1.0, float(win_rate))) * max(int(n), 0)))


def _wilson_interval(wins: int, n: int, *, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    n = max(int(n), 0)
    wins = max(int(wins), 0)
    if n <= 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    adj = (z / denom) * math.sqrt((p * (1 - p) / n) + (z**2) / (4 * n**2))
    return (max(0.0, center - adj), min(1.0, center + adj))


def _cohen_h(p_a: float, p_b: float) -> float:
    """Cohen's h for difference in proportions."""
    a = max(0.0, min(1.0, float(p_a)))
    b = max(0.0, min(1.0, float(p_b)))
    return 2.0 * math.asin(math.sqrt(b)) - 2.0 * math.asin(math.sqrt(a))


def _evidence_strength(*, is_significant: bool, total_n: int, effect_size: float) -> str:
    if not is_significant:
        return "weak"
    if total_n >= 200 and effect_size >= 0.5:
        return "strong"
    if total_n >= 50 and effect_size >= 0.2:
        return "moderate"
    return "weak"


def analyze_trend(
    variant_id: str,
    metrics_history: List[Dict[str, Any]],
    metric_name: str = "win_rate",
) -> TrendAnalysis:
    """Analyze performance trend over time for a variant.

    Uses linear regression + volatility analysis.
    """
    values = [
        float(m.get("metrics", {}).get(metric_name) or 0.0)
        for m in metrics_history
        if m.get("variant_id") == variant_id
    ]

    if len(values) < 2:
        return TrendAnalysis(
            variant_id=variant_id,
            metric_name=metric_name,
            values=values,
            trend_direction="insufficient_data",
            slope=0.0,
            r_squared=0.0,
            volatility=0.0,
            confidence=0.0,
        )

    n = len(values)
    x = list(range(n))
    mean_x = sum(x) / n
    mean_y = sum(values) / n

    # Linear regression
    numerator = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
    slope = numerator / denominator if denominator > 0 else 0.0

    # R-squared
    y_pred = [slope * xi + (mean_y - slope * mean_x) for xi in x]
    ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((values[i] - mean_y) ** 2 for i in range(n))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Volatility (coefficient of variation)
    std_dev = math.sqrt(sum((v - mean_y) ** 2 for v in values) / n)
    volatility = (std_dev / mean_y) if mean_y > 0 else 0.0

    # Trend direction
    if volatility > 0.3:
        direction = "volatile"
    elif abs(slope) < 0.01:
        direction = "stable"
    elif slope > 0:
        direction = "improving"
    else:
        direction = "declining"

    # Confidence (based on R² and sample size)
    confidence = min(r_squared * math.sqrt(n / 10), 1.0)

    return TrendAnalysis(
        variant_id=variant_id,
        metric_name=metric_name,
        values=values,
        trend_direction=direction,
        slope=slope,
        r_squared=r_squared,
        volatility=volatility,
        confidence=confidence,
    )


def detect_diminishing_returns(
    metrics_history: List[Dict[str, Any]],
    metric_name: str = "win_rate",
    threshold: float = 0.02,
) -> bool:
    """Detect if improvements are plateauing (diminishing returns).

    Returns True if recent improvements < threshold.
    """
    if len(metrics_history) < 3:
        return False

    recent = metrics_history[-3:]
    values = [float(m.get("metrics", {}).get(metric_name) or 0.0) for m in recent]

    max_improvement = max(values[i] - values[i - 1] for i in range(1, len(values)))
    return max_improvement < threshold


def _t_test_p_value(t_stat: float, df: float) -> float:
    """Approximate two-tailed p-value for t-statistic.

    Uses a simplified approximation. For production, use scipy.stats.t.sf.
    """
    if df < 1:
        return 1.0

    # Approximation: p ≈ 2 * (1 - Φ(t)) for large df
    # where Φ is the standard normal CDF
    z = t_stat
    p_one_tail = 0.5 * (1 - _erf(z / math.sqrt(2)))
    return 2 * p_one_tail


def _erf(x: float) -> float:
    """Approximate error function (for normal CDF)."""
    # Abramowitz and Stegun approximation
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return sign * y


__all__ = [
    "StatisticalResult",
    "TrendAnalysis",
    "compare_variants",
    "analyze_trend",
    "detect_diminishing_returns",
]
