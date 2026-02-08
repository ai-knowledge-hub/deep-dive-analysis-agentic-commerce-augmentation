"""ML Engine Trainer - Loads historical experiments and trains the ML engine.

This module runs on application startup to train the ML engine on historical data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from application.ports.deps import AppDeps
from application.services.experiment.ml import ExperimentMLEngine

logger = logging.getLogger(__name__)


class ExperimentMLTrainer:
    """Trains ML engine on historical experiment data."""

    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._engine = ExperimentMLEngine()
        self._is_trained = False

    @property
    def engine(self) -> ExperimentMLEngine:
        """Get the trained ML engine."""
        if not self._is_trained:
            logger.warning(
                "ML engine accessed before training. Call train() first for optimal results."
            )
        return self._engine

    def train(
        self, *, min_experiments: int = 5, max_experiments: int = 1000
    ) -> Dict[str, Any]:
        """Train the ML engine on historical experiments.

        Args:
            min_experiments: Minimum number of experiments required for training
            max_experiments: Maximum number of experiments to load (for performance)

        Returns:
            Training summary with statistics
        """
        logger.info("Starting ML engine training...")

        # Load historical experiments
        historical = self._load_historical_experiments(limit=max_experiments)

        if len(historical) < min_experiments:
            logger.warning(
                f"Insufficient training data: {len(historical)} experiments "
                f"(min required: {min_experiments}). Using fallback recommendations."
            )
            return {
                "success": False,
                "experiments_loaded": len(historical),
                "min_required": min_experiments,
                "message": "Insufficient data for training",
            }

        # Train the engine
        self._engine.fit(historical)
        self._is_trained = True

        # Compute training statistics
        stats = self._compute_training_stats(historical)

        logger.info(
            f"ML engine training complete. Loaded {len(historical)} experiments."
        )

        return {
            "success": True,
            "experiments_loaded": len(historical),
            "statistics": stats,
            "message": "Training successful",
        }

    def _load_historical_experiments(
        self, *, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Load historical experiments from database.

        Loads experiments with:
        - At least 2 variants
        - At least 1 variant with metrics
        - Product information
        """
        # Query experiments
        # Note: This assumes you have a method to query all experiments
        # You may need to add this to your experiments repository
        experiments = self._deps.experiments.list_all_experiments(
            status="completed", limit=limit
        )

        enriched = []
        for exp in experiments:
            try:
                # Load variants
                variants = self._deps.experiments.list_variants(experiment_id=exp["id"])
                if len(variants) < 2:
                    continue

                # Load metrics for each variant
                variants_with_metrics = []
                for variant in variants:
                    metrics_list = self._deps.experiment_runs.list_metrics(
                        experiment_id=exp["id"], variant_id=variant["id"], limit=1
                    )
                    if metrics_list:
                        variant_with_metrics = {
                            **variant,
                            "metrics": metrics_list[0].get("metrics"),
                        }
                        variants_with_metrics.append(variant_with_metrics)

                if len(variants_with_metrics) < 2:
                    continue

                # Load product
                product = None
                if exp.get("product_id"):
                    product = self._deps.clients.get_product_for_client(
                        client_id=exp["client_id"], product_id=exp["product_id"]
                    )

                if not product:
                    continue

                # Enrich experiment with full data
                enriched.append(
                    {
                        **exp,
                        "variants": variants_with_metrics,
                        "product": product,
                        "num_competitors": exp.get("competitor_policy", {})
                        .get("competitor_client_ids", [])
                        .__len__(),
                    }
                )

            except Exception as e:
                logger.warning(
                    f"Error loading experiment {exp.get('id')}: {e}. Skipping."
                )
                continue

        return enriched

    def _compute_training_stats(
        self, historical: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute statistics about the training data."""
        total_experiments = len(historical)
        total_variants = sum(len(exp.get("variants", [])) for exp in historical)

        # Intervention type distribution
        intervention_types: Dict[str, int] = {}
        for exp in historical:
            for variant in exp.get("variants", []):
                vtype = variant.get("type") or "unknown"
                intervention_types[vtype] = intervention_types.get(vtype, 0) + 1

        # Success rate by intervention type
        success_rates: Dict[str, List[float]] = {}
        for exp in historical:
            variants = exp.get("variants", [])
            if len(variants) < 2:
                continue

            baseline_win_rate = variants[0].get("metrics", {}).get("win_rate", 0.0)

            for variant in variants[1:]:
                vtype = variant.get("type") or "unknown"
                variant_win_rate = variant.get("metrics", {}).get("win_rate", 0.0)
                lift = variant_win_rate - baseline_win_rate

                if vtype not in success_rates:
                    success_rates[vtype] = []
                success_rates[vtype].append(lift)

        # Average lift by type
        avg_lift_by_type = {
            vtype: sum(lifts) / len(lifts) if lifts else 0.0
            for vtype, lifts in success_rates.items()
        }

        return {
            "total_experiments": total_experiments,
            "total_variants": total_variants,
            "intervention_type_distribution": intervention_types,
            "avg_lift_by_type": avg_lift_by_type,
            "patterns_learned": len(self._engine._pattern_weights),
        }


def create_global_trainer(deps: AppDeps) -> ExperimentMLTrainer:
    """Create and train a global ML trainer instance.

    This should be called once on application startup.
    """
    trainer = ExperimentMLTrainer(deps=deps)

    try:
        result = trainer.train(min_experiments=5)
        if result["success"]:
            logger.info(f"ML trainer initialized: {result['message']}")
        else:
            logger.warning(f"ML trainer fallback mode: {result['message']}")
    except Exception as e:
        logger.error(f"Failed to train ML engine: {e}. Using fallback mode.")

    return trainer


__all__ = ["ExperimentMLTrainer", "create_global_trainer"]
