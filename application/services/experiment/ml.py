"""ML-based pattern recognition for experiment recommendations.

Uses historical experiment data to learn what works and predict
the most promising next hypothesis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class HypothesisRecommendation:
    """ML-generated hypothesis recommendation."""

    hypothesis_type: str  # "copy", "tone", "protocol", "mixed"
    predicted_lift: float  # expected improvement
    confidence: float  # 0-1
    rationale: str
    suggested_payload: Dict[str, Any]
    similar_experiments: List[str]  # IDs of similar past experiments


@dataclass(frozen=True)
class ExperimentFeatures:
    """Feature vector for ML model."""

    # Product features
    product_type: str
    product_complexity: float  # 0-1 (derived from description length, attributes)
    has_technical_specs: bool
    has_outcome_language: bool

    # Experiment context
    baseline_win_rate: float
    baseline_avg_score: float
    num_competitors: int

    # Intervention features
    intervention_type: str
    changed_outcome_framing: bool
    changed_technical_detail: bool
    changed_tone: bool

    # Results
    win_rate_lift: float
    avg_score_lift: float
    protocol_readiness_delta: float


class ExperimentMLEngine:
    """ML-based experiment recommendation engine.

    Uses historical experiment data to learn patterns and predict
    the most promising next hypothesis.
    """

    def __init__(self) -> None:
        self._feature_db: List[ExperimentFeatures] = []
        self._pattern_weights: Dict[str, float] = {}

    def fit(self, experiments: List[Dict[str, Any]]) -> None:
        """Train the model on historical experiment data."""
        self._feature_db = []

        for exp in experiments:
            features = self._extract_features(exp)
            if features:
                self._feature_db.append(features)

        self._learn_patterns()

    def predict_best_hypothesis(
        self,
        current_experiment: Dict[str, Any],
        product: Dict[str, Any],
        brand_beliefs: List[Dict[str, Any]],
    ) -> HypothesisRecommendation:
        """Predict the most promising hypothesis for the next variant."""
        if not self._feature_db:
            return self._fallback_recommendation(product, brand_beliefs)

        # Extract features from current state
        current_features = self._extract_current_features(current_experiment, product)

        # Find similar past experiments
        similar = self._find_similar_experiments(current_features, top_k=5)

        if not similar:
            return self._fallback_recommendation(product, brand_beliefs)

        # Aggregate insights from similar experiments
        best_intervention_type = self._vote_on_intervention_type(similar)
        predicted_lift = self._predict_lift(similar, best_intervention_type)

        # Generate hypothesis based on patterns + beliefs
        hypothesis = self._generate_hypothesis(
            intervention_type=best_intervention_type,
            product=product,
            similar_experiments=similar,
            brand_beliefs=brand_beliefs,
        )

        confidence = self._calculate_confidence(similar, best_intervention_type)

        return HypothesisRecommendation(
            hypothesis_type=best_intervention_type,
            predicted_lift=predicted_lift,
            confidence=confidence,
            rationale=hypothesis["rationale"],
            suggested_payload=hypothesis["payload"],
            similar_experiments=[exp.get("id") or "" for exp, _ in similar],
        )

    def _extract_features(
        self, experiment: Dict[str, Any]
    ) -> Optional[ExperimentFeatures]:
        """Extract feature vector from experiment record."""
        variants = experiment.get("variants") or []
        if len(variants) < 2:
            return None

        baseline = variants[0]
        variant = variants[1]

        baseline_metrics = baseline.get("metrics") or {}
        variant_metrics = variant.get("metrics") or {}

        product = experiment.get("product") or {}
        description = product.get("description") or ""

        return ExperimentFeatures(
            product_type=self._infer_product_type(description),
            product_complexity=self._calculate_complexity(description),
            has_technical_specs=self._has_technical_specs(description),
            has_outcome_language=self._has_outcome_language(description),
            baseline_win_rate=float(baseline_metrics.get("win_rate") or 0.0),
            baseline_avg_score=float(baseline_metrics.get("avg_score") or 0.0),
            num_competitors=experiment.get("num_competitors") or 3,
            intervention_type=variant.get("type") or "copy",
            changed_outcome_framing=self._detect_outcome_framing_change(
                baseline, variant
            ),
            changed_technical_detail=self._detect_technical_change(baseline, variant),
            changed_tone=self._detect_tone_change(baseline, variant),
            win_rate_lift=float(variant_metrics.get("win_rate") or 0.0)
            - float(baseline_metrics.get("win_rate") or 0.0),
            avg_score_lift=float(variant_metrics.get("avg_score") or 0.0)
            - float(baseline_metrics.get("avg_score") or 0.0),
            protocol_readiness_delta=0.0,  # TODO: extract from results
        )

    def _extract_current_features(
        self, experiment: Dict[str, Any], product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features from current experiment state."""
        description = product.get("description") or ""
        latest_metrics = self._get_latest_metrics(experiment)

        return {
            "product_type": self._infer_product_type(description),
            "product_complexity": self._calculate_complexity(description),
            "has_technical_specs": self._has_technical_specs(description),
            "has_outcome_language": self._has_outcome_language(description),
            "baseline_win_rate": float(latest_metrics.get("win_rate") or 0.0),
            "baseline_avg_score": float(latest_metrics.get("avg_score") or 0.0),
        }

    def _find_similar_experiments(
        self, current: Dict[str, Any], top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Find similar past experiments using cosine similarity."""
        scored = []
        for features in self._feature_db:
            similarity = self._compute_similarity(current, features)
            scored.append((features, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self._features_to_dict(f), s) for f, s in scored[:top_k]]

    def _compute_similarity(
        self, current: Dict[str, Any], past: ExperimentFeatures
    ) -> float:
        """Compute similarity between current state and past experiment."""
        score = 0.0

        # Product type match
        if current.get("product_type") == past.product_type:
            score += 0.3

        # Complexity similarity
        complexity_diff = abs(
            current.get("product_complexity", 0.5) - past.product_complexity
        )
        score += 0.2 * (1 - complexity_diff)

        # Feature matches
        if current.get("has_technical_specs") == past.has_technical_specs:
            score += 0.15
        if current.get("has_outcome_language") == past.has_outcome_language:
            score += 0.15

        # Performance similarity
        win_rate_diff = abs(
            current.get("baseline_win_rate", 0.5) - past.baseline_win_rate
        )
        score += 0.2 * (1 - win_rate_diff)

        return score

    def _vote_on_intervention_type(
        self, similar: List[Tuple[Dict[str, Any], float]]
    ) -> str:
        """Vote on intervention type based on weighted success."""
        votes: Dict[str, float] = {}

        for exp, similarity in similar:
            intervention = exp.get("intervention_type") or "copy"
            lift = exp.get("win_rate_lift") or 0.0

            if lift > 0.05:  # Only count successful experiments
                votes[intervention] = votes.get(intervention, 0) + similarity * lift

        if not votes:
            return "copy"

        return max(votes, key=votes.get)  # type: ignore

    def _predict_lift(
        self, similar: List[Tuple[Dict[str, Any], float]], intervention_type: str
    ) -> float:
        """Predict expected lift based on similar experiments."""
        relevant = [
            exp
            for exp, _ in similar
            if exp.get("intervention_type") == intervention_type
        ]

        if not relevant:
            return 0.05  # default conservative estimate

        lifts = [exp.get("win_rate_lift") or 0.0 for exp in relevant]
        return sum(lifts) / len(lifts)

    def _generate_hypothesis(
        self,
        intervention_type: str,
        product: Dict[str, Any],
        similar_experiments: List[Tuple[Dict[str, Any], float]],
        brand_beliefs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate hypothesis with rationale and suggested payload."""
        description = product.get("description") or ""

        # Check brand beliefs for relevant patterns
        belief_insights = self._extract_belief_insights(
            brand_beliefs, intervention_type
        )

        if intervention_type == "copy" and not self._has_outcome_language(description):
            rationale = (
                "Based on similar successful experiments, adding outcome-focused "
                "language improves win-rate. Your current copy lacks outcome framing."
            )
            if belief_insights:
                rationale += f" {belief_insights}"

            payload = {
                "description": self._suggest_outcome_framing(description),
                "change_type": "add_outcome_framing",
            }

        elif intervention_type == "copy" and self._has_technical_specs(description):
            rationale = (
                "Similar products with technical specs benefited from adding "
                "context-fit language (use cases, problems solved)."
            )
            if belief_insights:
                rationale += f" {belief_insights}"

            payload = {
                "description": self._suggest_context_addition(description),
                "change_type": "add_context_fit",
            }

        else:
            rationale = (
                f"Based on {len(similar_experiments)} similar experiments, "
                f"{intervention_type} interventions show promise."
            )
            payload = {
                "description": description,
                "change_type": "general_optimization",
            }

        return {"rationale": rationale, "payload": payload}

    def _calculate_confidence(
        self, similar: List[Tuple[Dict[str, Any], float]], intervention_type: str
    ) -> float:
        """Calculate confidence in recommendation."""
        if not similar:
            return 0.2

        relevant = [
            exp
            for exp, sim in similar
            if exp.get("intervention_type") == intervention_type
        ]

        if not relevant:
            return 0.3

        # Confidence based on: number of similar experiments, avg similarity, avg lift
        n = len(relevant)
        avg_similarity = sum(sim for _, sim in similar[:n]) / n
        avg_lift = sum(exp.get("win_rate_lift") or 0.0 for exp in relevant) / n

        confidence = min(
            0.4 + 0.3 * math.sqrt(n / 10) + 0.2 * avg_similarity + 0.1 * avg_lift, 1.0
        )
        return round(confidence, 2)

    def _learn_patterns(self) -> None:
        """Learn patterns from feature database (placeholder for future ML model)."""
        # For now, compute simple pattern weights
        self._pattern_weights = {
            "outcome_framing_adds_lift": self._compute_pattern_weight(
                "changed_outcome_framing"
            ),
            "technical_reduction_helps": self._compute_pattern_weight(
                "changed_technical_detail"
            ),
            "tone_matters": self._compute_pattern_weight("changed_tone"),
        }

    def _compute_pattern_weight(self, feature: str) -> float:
        """Compute weight of a specific pattern."""
        if not self._feature_db:
            return 0.0

        positive = [
            f
            for f in self._feature_db
            if getattr(f, feature, False) and f.win_rate_lift > 0.05
        ]
        total = [f for f in self._feature_db if getattr(f, feature, False)]

        return len(positive) / len(total) if total else 0.0

    def _fallback_recommendation(
        self, product: Dict[str, Any], brand_beliefs: List[Dict[str, Any]]
    ) -> HypothesisRecommendation:
        """Fallback when no historical data is available."""
        description = product.get("description") or ""

        # Extract belief insights for fallback
        belief_insight = self._extract_belief_insights(brand_beliefs, "copy")

        if not self._has_outcome_language(description):
            rationale = "Standard pattern: products without outcome framing benefit from adding user-goal language."
            if belief_insight:
                rationale += f" {belief_insight}"

            return HypothesisRecommendation(
                hypothesis_type="copy",
                predicted_lift=0.1,
                confidence=0.4,
                rationale=rationale,
                suggested_payload={
                    "description": self._suggest_outcome_framing(description),
                    "change_type": "add_outcome_framing",
                },
                similar_experiments=[],
            )

        rationale = "Insufficient historical data. Recommend general optimization."
        if belief_insight:
            rationale += f" {belief_insight}"

        return HypothesisRecommendation(
            hypothesis_type="copy",
            predicted_lift=0.05,
            confidence=0.3,
            rationale=rationale,
            suggested_payload={"description": description, "change_type": "general"},
            similar_experiments=[],
        )

    # --- Helper methods ---

    def _infer_product_type(self, description: str) -> str:
        """Infer product category from description."""
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["tv", "screen", "display", "monitor"]):
            return "electronics_display"
        if any(kw in desc_lower for kw in ["shoe", "sneaker", "boot", "footwear"]):
            return "footwear"
        if any(kw in desc_lower for kw in ["vest", "jacket", "apparel", "clothing"]):
            return "apparel"
        return "general"

    def _calculate_complexity(self, description: str) -> float:
        """Estimate product complexity (0-1) based on description."""
        words = description.split()
        technical_terms = sum(
            1
            for w in words
            if any(char.isdigit() for char in w)  # contains numbers (specs)
        )
        return min(technical_terms / max(len(words), 1), 1.0)

    def _has_technical_specs(self, description: str) -> bool:
        """Check if description contains technical specifications."""
        spec_indicators = ["inch", "gb", "mhz", "watts", "nits", "mm", "kg", "lbs"]
        desc_lower = description.lower()
        return any(spec in desc_lower for spec in spec_indicators)

    def _has_outcome_language(self, description: str) -> bool:
        """Check if description uses outcome-focused language."""
        outcome_indicators = [
            "enable",
            "achieve",
            "combat",
            "reduce",
            "improve",
            "help",
            "solve",
            "without",
            "easily",
        ]
        desc_lower = description.lower()
        return any(word in desc_lower for word in outcome_indicators)

    def _detect_outcome_framing_change(
        self, baseline: Dict[str, Any], variant: Dict[str, Any]
    ) -> bool:
        """Detect if variant added outcome framing."""
        baseline_desc = baseline.get("payload", {}).get("description") or ""
        variant_desc = variant.get("payload", {}).get("description") or ""

        return self._has_outcome_language(
            variant_desc
        ) and not self._has_outcome_language(baseline_desc)

    def _detect_technical_change(
        self, baseline: Dict[str, Any], variant: Dict[str, Any]
    ) -> bool:
        """Detect if technical detail level changed."""
        baseline_desc = baseline.get("payload", {}).get("description") or ""
        variant_desc = variant.get("payload", {}).get("description") or ""

        return self._calculate_complexity(variant_desc) != self._calculate_complexity(
            baseline_desc
        )

    def _detect_tone_change(
        self, baseline: Dict[str, Any], variant: Dict[str, Any]
    ) -> bool:
        """Detect if tone changed significantly."""
        # Simplified: check if length changed significantly or new keywords added
        baseline_desc = baseline.get("payload", {}).get("description") or ""
        variant_desc = variant.get("payload", {}).get("description") or ""

        return abs(len(variant_desc) - len(baseline_desc)) > 50

    def _get_latest_metrics(self, experiment: Dict[str, Any]) -> Dict[str, Any]:
        """Get latest metrics from experiment."""
        metrics = experiment.get("metrics") or []
        if not metrics:
            return {}
        latest = max(metrics, key=lambda m: m.get("created_at") or "")
        return latest.get("metrics") or {}

    def _suggest_outcome_framing(self, description: str) -> str:
        """Suggest outcome-focused rewrite (placeholder for LLM call)."""
        # In production, call LLM with prompt template
        return f"{description} [Add outcome-focused language here]"

    def _suggest_context_addition(self, description: str) -> str:
        """Suggest context-fit addition (placeholder for LLM call)."""
        return f"{description} [Add use case / problem-solving context here]"

    def _extract_belief_insights(
        self, beliefs: List[Dict[str, Any]], intervention_type: str
    ) -> str:
        """Extract relevant insights from brand beliefs."""
        if not beliefs:
            return ""

        relevant = [
            b
            for b in beliefs
            if intervention_type in (b.get("metadata", {}).get("variant_type") or "")
        ]

        if relevant:
            top_belief = max(relevant, key=lambda b: b.get("confidence") or 0.0)
            return f"Brand belief: {top_belief.get('recommendation') or 'No specific insight.'}"

        return ""

    def _features_to_dict(self, features: ExperimentFeatures) -> Dict[str, Any]:
        """Convert ExperimentFeatures to dict."""
        return {
            "product_type": features.product_type,
            "product_complexity": features.product_complexity,
            "has_technical_specs": features.has_technical_specs,
            "has_outcome_language": features.has_outcome_language,
            "baseline_win_rate": features.baseline_win_rate,
            "baseline_avg_score": features.baseline_avg_score,
            "num_competitors": features.num_competitors,
            "intervention_type": features.intervention_type,
            "changed_outcome_framing": features.changed_outcome_framing,
            "changed_technical_detail": features.changed_technical_detail,
            "changed_tone": features.changed_tone,
            "win_rate_lift": features.win_rate_lift,
            "avg_score_lift": features.avg_score_lift,
            "protocol_readiness_delta": features.protocol_readiness_delta,
        }


__all__ = ["ExperimentMLEngine", "HypothesisRecommendation", "ExperimentFeatures"]
