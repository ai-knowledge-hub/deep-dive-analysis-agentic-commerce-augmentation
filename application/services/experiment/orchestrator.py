"""Enhanced Experiment Orchestrator with ML-based recommendations.

Uses statistical significance testing, ML pattern recognition, brand beliefs,
and Thompson Sampling for exploration/exploitation trade-offs.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.experiment.ml import (
    ExperimentMLEngine,
    HypothesisRecommendation,
)
from application.services.experiment.statistics import (
    StatisticalResult,
    compare_variants,
    detect_diminishing_returns,
)


@dataclass(frozen=True)
class NextTestRecommendation:
    """Recommendation for the next experiment action."""

    experiment_id: str
    action: str  # "run_variant", "create_variant", "stop", "none"
    reason: str
    variant_id: Optional[str] = None
    confidence: Optional[float] = None
    suggested_label: Optional[str] = None
    suggested_type: Optional[str] = None
    suggested_payload: Optional[Dict[str, Any]] = None

    # Enhanced fields
    statistical_analysis: Optional[Dict[str, Any]] = None
    ml_prediction: Optional[Dict[str, Any]] = None
    exploration_score: Optional[float] = None
    exploitation_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "action": self.action,
            "reason": self.reason,
            "variant_id": self.variant_id,
            "confidence": self.confidence,
            "suggested_label": self.suggested_label,
            "suggested_type": self.suggested_type,
            "suggested_payload": self.suggested_payload,
            "statistical_analysis": self.statistical_analysis,
            "ml_prediction": self.ml_prediction,
            "exploration_score": self.exploration_score,
            "exploitation_score": self.exploitation_score,
        }


class ExperimentOrchestrator:
    """Enhanced orchestrator with ML-based recommendations and Thompson Sampling."""

    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._ml_engine = ExperimentMLEngine()
        self._initialize_ml_engine()

    def suggest_next_test(
        self, *, experiment_id: str, client_id: str, user_id: Optional[str] = None
    ) -> NextTestRecommendation:
        """Suggest the next best action using ML + statistical analysis."""
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")

        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        metrics = self._deps.experiment_runs.list_metrics(experiment_id=experiment_id)

        # Early exit cases
        if not variants:
            return self._recommend_first_variant(experiment)

        if len(variants) == 1:
            return self._recommend_second_variant(experiment, variants[0])

        # Build metrics map
        metrics_by_variant = self._build_metrics_map(metrics)
        missing_metrics = self._find_untested_variants(variants, metrics_by_variant)

        if missing_metrics:
            return self._recommend_run_untested(missing_metrics[0])

        # Statistical analysis
        stat_result = self._analyze_variants_statistically(
            variants, metrics_by_variant, metrics
        )

        # Check for stopping conditions
        stop_recommendation = self._check_stopping_conditions(
            stat_result, metrics, metrics_by_variant
        )
        if stop_recommendation:
            return stop_recommendation

        # ML-based recommendation
        product = self._get_product_for_experiment(experiment, client_id)
        brand_beliefs = self._get_brand_beliefs(experiment, client_id, user_id)

        ml_recommendation = self._get_ml_recommendation(
            experiment, product, brand_beliefs
        )

        # Thompson Sampling: exploration vs. exploitation
        thompson_choice = self._thompson_sampling(variants, metrics_by_variant)

        # Combine signals to make final recommendation
        return self._make_final_recommendation(
            experiment=experiment,
            variants=variants,
            stat_result=stat_result,
            ml_recommendation=ml_recommendation,
            thompson_choice=thompson_choice,
            metrics_by_variant=metrics_by_variant,
        )

    def _initialize_ml_engine(self) -> None:
        """Load historical experiment data into ML engine."""
        # TODO: Load all past experiments from DB
        # For now, the engine will use fallback recommendations
        pass

    def _recommend_first_variant(
        self, experiment: Dict[str, Any]
    ) -> NextTestRecommendation:
        """Recommend creating the first baseline variant."""
        suggested_payload = _derive_payload(experiment.get("hypothesis") or {})
        return NextTestRecommendation(
            experiment_id=experiment["id"],
            action="create_variant",
            reason="Experiment has no variants. Start by creating a baseline (control) variant.",
            confidence=0.9,
            suggested_label="Control (baseline)",
            suggested_type="copy",
            suggested_payload=suggested_payload or {},
        )

    def _recommend_second_variant(
        self, experiment: Dict[str, Any], baseline: Dict[str, Any]
    ) -> NextTestRecommendation:
        """Recommend creating the hypothesis variant."""
        suggested_payload = _derive_payload(experiment.get("hypothesis") or {})
        return NextTestRecommendation(
            experiment_id=experiment["id"],
            action="create_variant",
            reason="Only one variant exists. Create a hypothesis variant to test against the baseline.",
            confidence=0.85,
            suggested_label="Hypothesis (variant A)",
            suggested_type="copy",
            suggested_payload=suggested_payload,
        )

    def _recommend_run_untested(
        self, variant: Dict[str, Any]
    ) -> NextTestRecommendation:
        """Recommend running an untested variant."""
        return NextTestRecommendation(
            experiment_id=variant.get("experiment_id") or "",
            action="run_variant",
            variant_id=variant.get("id"),
            reason=f"Variant '{variant.get('label')}' has no test results yet. Run it to gather baseline data.",
            confidence=0.8,
        )

    def _analyze_variants_statistically(
        self,
        variants: List[Dict[str, Any]],
        metrics_by_variant: Dict[str, Dict[str, Any]],
        all_metrics: List[Dict[str, Any]],
    ) -> Optional[StatisticalResult]:
        """Perform statistical comparison between top variants."""
        if len(variants) < 2:
            return None

        # Find best and second-best variants
        ranked = sorted(
            [
                (v, metrics_by_variant.get(v["id"]))
                for v in variants
                if v["id"] in metrics_by_variant
            ],
            key=lambda x: self._variant_score(x[1]),
            reverse=True,
        )

        if len(ranked) < 2:
            return None

        best_variant, best_metrics = ranked[0]
        second_variant, second_metrics = ranked[1]

        # Add metrics to variant dicts for comparison
        best_with_metrics = {**best_variant, "metrics": best_metrics.get("metrics")}
        second_with_metrics = {
            **second_variant,
            "metrics": second_metrics.get("metrics"),
        }

        return compare_variants(best_with_metrics, second_with_metrics, "win_rate")

    def _check_stopping_conditions(
        self,
        stat_result: Optional[StatisticalResult],
        all_metrics: List[Dict[str, Any]],
        metrics_by_variant: Dict[str, Dict[str, Any]],
    ) -> Optional[NextTestRecommendation]:
        """Check if we should stop testing (winner found or diminishing returns)."""
        if not stat_result:
            return None

        # Stopping condition 1: Clear winner with high confidence
        if (
            stat_result.is_significant
            and abs(stat_result.effect_size) > 0.5
            and stat_result.evidence_strength in {"moderate", "strong"}
        ):
            winner_id = (
                stat_result.variant_b_id
                if stat_result.difference > 0
                else stat_result.variant_a_id
            )
            return NextTestRecommendation(
                experiment_id="",  # Will be filled by caller
                action="stop",
                reason=(
                    f"Clear winner identified: {winner_id}. "
                    f"Effect size: {abs(stat_result.effect_size):.2f}, "
                    f"evidence: {stat_result.evidence_strength}. "
                    "Recommend deploying winner and concluding experiment."
                ),
                confidence=0.95,
                variant_id=winner_id,
                statistical_analysis=self._stat_result_to_dict(stat_result),
            )

        # Stopping condition 2: Diminishing returns
        if detect_diminishing_returns(all_metrics, threshold=0.02):
            best_variant_id = max(
                metrics_by_variant.keys(),
                key=lambda vid: self._variant_score(metrics_by_variant[vid]),
            )
            return NextTestRecommendation(
                experiment_id="",
                action="stop",
                reason=(
                    "Diminishing returns detected: recent improvements < 2%. "
                    "Recommend deploying current best variant and exploring new hypothesis."
                ),
                confidence=0.75,
                variant_id=best_variant_id,
            )

        return None

    def _get_ml_recommendation(
        self,
        experiment: Dict[str, Any],
        product: Optional[Dict[str, Any]],
        brand_beliefs: List[Dict[str, Any]],
    ) -> Optional[HypothesisRecommendation]:
        """Get ML-based hypothesis recommendation."""
        if not product:
            return None

        try:
            return self._ml_engine.predict_best_hypothesis(
                current_experiment=experiment,
                product=product,
                brand_beliefs=brand_beliefs,
            )
        except Exception:
            return None

    def _thompson_sampling(
        self,
        variants: List[Dict[str, Any]],
        metrics_by_variant: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Use Thompson Sampling to balance exploration/exploitation.

        Returns the variant that should be tested next, considering both:
        - Exploitation: variants with high current performance
        - Exploration: variants with high uncertainty (few runs)
        """
        samples = []

        for variant in variants:
            vid = variant["id"]
            metrics = metrics_by_variant.get(vid)

            if not metrics:
                # High exploration value for untested variants
                samples.append(
                    {
                        "variant_id": vid,
                        "sample": 0.5,  # neutral prior
                        "exploration_score": 1.0,
                        "exploitation_score": 0.0,
                    }
                )
                continue

            payload = metrics.get("metrics") or {}
            wins = int(payload.get("wins") or 0)
            total = int(payload.get("total_runs") or 1)

            # Beta distribution: Beta(wins + 1, losses + 1)
            alpha = wins + 1
            beta = (total - wins) + 1

            # Sample from Beta distribution (Thompson Sampling)
            sample = self._beta_sample(alpha, beta)

            # Exploration score: higher for fewer samples
            exploration_score = 1.0 / math.sqrt(max(total, 1))

            # Exploitation score: current win rate
            exploitation_score = wins / total if total > 0 else 0.0

            samples.append(
                {
                    "variant_id": vid,
                    "sample": sample,
                    "exploration_score": exploration_score,
                    "exploitation_score": exploitation_score,
                    "alpha": alpha,
                    "beta": beta,
                }
            )

        # Select variant with highest sample
        best = max(samples, key=lambda x: x["sample"])
        return best

    def _make_final_recommendation(
        self,
        experiment: Dict[str, Any],
        variants: List[Dict[str, Any]],
        stat_result: Optional[StatisticalResult],
        ml_recommendation: Optional[HypothesisRecommendation],
        thompson_choice: Dict[str, Any],
        metrics_by_variant: Dict[str, Dict[str, Any]],
    ) -> NextTestRecommendation:
        """Combine all signals to make final recommendation."""

        # Priority 1: If ML suggests creating a new variant with high confidence
        if ml_recommendation and ml_recommendation.confidence > 0.6:
            return NextTestRecommendation(
                experiment_id=experiment["id"],
                action="create_variant",
                reason=ml_recommendation.rationale,
                confidence=ml_recommendation.confidence,
                suggested_label=f"ML Hypothesis ({ml_recommendation.hypothesis_type})",
                suggested_type=ml_recommendation.hypothesis_type,
                suggested_payload=ml_recommendation.suggested_payload,
                ml_prediction=self._ml_recommendation_to_dict(ml_recommendation),
            )

        # Priority 2: Thompson Sampling suggests variant to explore
        if thompson_choice["exploration_score"] > 0.3:
            variant = next(
                (v for v in variants if v["id"] == thompson_choice["variant_id"]), None
            )
            if variant:
                return NextTestRecommendation(
                    experiment_id=experiment["id"],
                    action="run_variant",
                    variant_id=variant["id"],
                    reason=(
                        f"Thompson Sampling recommends exploring variant '{variant.get('label')}'. "
                        f"Exploration score: {thompson_choice['exploration_score']:.2f}, "
                        f"exploitation score: {thompson_choice['exploitation_score']:.2f}."
                    ),
                    confidence=0.7,
                    exploration_score=thompson_choice["exploration_score"],
                    exploitation_score=thompson_choice["exploitation_score"],
                )

        # Priority 3: Statistical analysis suggests re-running for significance
        if stat_result and not stat_result.is_significant:
            if stat_result.variant_a_n + stat_result.variant_b_n < 20:
                return NextTestRecommendation(
                    experiment_id=experiment["id"],
                    action="run_variant",
                    variant_id=stat_result.variant_b_id,
                    reason=(
                        "Insufficient data for statistical significance. "
                        f"Current sample size: {stat_result.variant_a_n + stat_result.variant_b_n}, "
                        "recommended: 20+. Re-run to increase confidence."
                    ),
                    confidence=0.65,
                    statistical_analysis=self._stat_result_to_dict(stat_result),
                )

        # Priority 4: ML suggests new variant (medium confidence)
        if ml_recommendation:
            return NextTestRecommendation(
                experiment_id=experiment["id"],
                action="create_variant",
                reason=ml_recommendation.rationale,
                confidence=ml_recommendation.confidence,
                suggested_label=f"Hypothesis ({ml_recommendation.hypothesis_type})",
                suggested_type=ml_recommendation.hypothesis_type,
                suggested_payload=ml_recommendation.suggested_payload,
                ml_prediction=self._ml_recommendation_to_dict(ml_recommendation),
            )

        # Fallback: run weakest variant
        weakest_id = min(
            metrics_by_variant.keys(),
            key=lambda vid: self._variant_score(metrics_by_variant[vid]),
        )
        weakest_variant = next((v for v in variants if v["id"] == weakest_id), None)

        if weakest_variant:
            return NextTestRecommendation(
                experiment_id=experiment["id"],
                action="run_variant",
                variant_id=weakest_id,
                reason=f"Re-run weakest variant '{weakest_variant.get('label')}' to confirm low performance.",
                confidence=0.5,
            )

        # Ultimate fallback
        return NextTestRecommendation(
            experiment_id=experiment["id"],
            action="none",
            reason="No clear recommendation. Consider manual review or new hypothesis.",
            confidence=0.2,
        )

    # --- Helper methods ---

    def _build_metrics_map(
        self, metrics: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Build map of variant_id -> latest metrics."""
        latest_by_variant: Dict[str, Dict[str, Any]] = {}
        for metric in metrics:
            variant_id = metric.get("variant_id")
            if not variant_id:
                continue
            existing = latest_by_variant.get(variant_id)
            if not existing or (metric.get("created_at") or "") > (
                existing.get("created_at") or ""
            ):
                latest_by_variant[variant_id] = metric
        return latest_by_variant

    def _find_untested_variants(
        self,
        variants: List[Dict[str, Any]],
        metrics_by_variant: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Find variants that haven't been tested yet."""
        return [v for v in variants if v.get("id") not in metrics_by_variant]

    def _variant_score(self, metrics: Dict[str, Any]) -> float:
        """Compute combined score for a variant."""
        payload = metrics.get("metrics") or {}
        win_rate = float(payload.get("win_rate") or 0.0)
        win_rate_robust = float(payload.get("win_rate_robust") or 0.0)
        judge_consensus = payload.get("judge_consensus_win_rate")
        judge_consensus = (
            float(judge_consensus) if judge_consensus is not None else None
        )
        avg_score = float(payload.get("avg_score") or 0.0)
        # Prefer robust win rate when available (winner under both semantic + keyword scoring).
        base = win_rate_robust * 0.6 + win_rate * 0.3 + avg_score * 0.1
        if judge_consensus is not None:
            return base * 0.8 + judge_consensus * 0.2
        return base

    def _get_product_for_experiment(
        self, experiment: Dict[str, Any], client_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the product associated with this experiment."""
        product_id = experiment.get("product_id")
        if not product_id:
            return None
        return self._deps.clients.get_product_for_client(
            client_id=client_id, product_id=product_id
        )

    def _get_brand_beliefs(
        self, experiment: Dict[str, Any], client_id: str, user_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get brand beliefs for this experiment."""
        brand_id = experiment.get("brand_id")
        if not brand_id:
            return []
        return self._deps.brand_beliefs.list_beliefs(
            client_id=client_id, brand_id=brand_id
        )

    def _beta_sample(self, alpha: float, beta: float) -> float:
        """Sample from Beta distribution (simplified approximation)."""
        # For production, use numpy.random.beta(alpha, beta)
        # Here's a simple approximation using gamma samples
        if alpha <= 0 or beta <= 0:
            return 0.5

        # Approximate using mean + noise
        mean = alpha / (alpha + beta)
        variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        noise = random.gauss(0, math.sqrt(variance))
        return max(0.0, min(1.0, mean + noise))

    def _stat_result_to_dict(self, result: StatisticalResult) -> Dict[str, Any]:
        """Convert StatisticalResult to dict."""
        return {
            "variant_a_id": result.variant_a_id,
            "variant_b_id": result.variant_b_id,
            "metric_name": result.metric_name,
            "difference": result.difference,
            "effect_size": result.effect_size,
            "confidence_interval": result.confidence_interval,
            "p_value": result.p_value,
            "is_significant": result.is_significant,
            "recommended_action": result.recommended_action,
            "evidence_strength": result.evidence_strength,
        }

    def _ml_recommendation_to_dict(
        self, rec: HypothesisRecommendation
    ) -> Dict[str, Any]:
        """Convert HypothesisRecommendation to dict."""
        return {
            "hypothesis_type": rec.hypothesis_type,
            "predicted_lift": rec.predicted_lift,
            "confidence": rec.confidence,
            "rationale": rec.rationale,
            "similar_experiments": rec.similar_experiments,
        }


def _derive_payload(hypothesis: Dict[str, Any]) -> Dict[str, Any]:
    """Extract payload from hypothesis JSON."""
    if not hypothesis:
        return {}
    variant_payload = hypothesis.get("variant_payload")
    if isinstance(variant_payload, dict):
        return variant_payload
    payload = hypothesis.get("payload")
    if isinstance(payload, dict):
        return payload
    proposed_copy = hypothesis.get("proposed_copy")
    if isinstance(proposed_copy, str) and proposed_copy:
        return {"description": proposed_copy}
    return {}


__all__ = ["ExperimentOrchestrator", "NextTestRecommendation"]
