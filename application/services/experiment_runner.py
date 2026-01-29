from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.simulation_service import SimulationService
from domain.simulation.ranking import score_for_product
from domain.simulation.types import SimulationProduct


@dataclass
class ExperimentRunResult:
    experiment_id: str
    variant_id: str
    runs: List[Dict[str, Any]]
    metrics: Dict[str, Any]


class ExperimentRunner:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._simulation = SimulationService(deps=deps)

    def run_experiment(
        self,
        *,
        experiment_id: str,
        variant_id: str,
        client_id: str,
        user_id: Optional[str] = None,
    ) -> ExperimentRunResult:
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")

        if experiment.get("battery_id") is None:
            raise ValueError("experiment missing battery_id")

        variant = self._deps.experiments.get_variant(variant_id=variant_id)
        if not variant or variant.get("experiment_id") != experiment_id:
            raise ValueError("variant not found for experiment")

        battery_id = experiment["battery_id"]
        queries = self._deps.query_batteries.list_queries(battery_id=battery_id)
        enabled_queries = [q for q in queries if q.get("enabled")]
        if not enabled_queries:
            raise ValueError("battery has no enabled queries")

        product = self._deps.clients.get_product_for_client(
            client_id=client_id, product_id=experiment["product_id"]
        )
        if not product:
            raise ValueError("product not found for client")

        competitor_policy = experiment.get("competitor_policy") or {}
        competitor_client_ids = competitor_policy.get("competitor_client_ids")

        self._deps.experiments.update_experiment(
            experiment_id=experiment_id, client_id=client_id, status="running"
        )

        runs_payload: List[Dict[str, Any]] = []
        scores: List[float] = []
        wins = 0

        for query in enabled_queries:
            sim_product, raw_product = _build_variant_product(
                product=product, variant=variant
            )
            response = self._simulation.run(
                query=query["query_text"],
                products=[sim_product],
                client_id=client_id,
                user_id=user_id,
                brand_id=experiment.get("brand_id"),
                product_id=experiment.get("product_id"),
                raw_products=[raw_product],
                auto_competitors=True,
                competitor_client_ids=competitor_client_ids,
            )
            run_id = response.get("run_id")
            result = response.get("result") or {}
            winner_id = result.get("winner_id")
            score = score_for_product(result.get("scores", []), product["id"])
            if score is not None:
                scores.append(score)
            if winner_id == product["id"]:
                wins += 1

            self._deps.experiment_runs.create_run(
                experiment_id=experiment_id,
                variant_id=variant_id,
                query_id=query["id"],
                simulation_run_id=run_id,
            )

            runs_payload.append(
                {
                    "query_id": query["id"],
                    "query_text": query["query_text"],
                    "run_id": run_id,
                    "winner_id": winner_id,
                    "score": score,
                }
            )

        total = len(enabled_queries)
        win_rate = (wins / total) if total else 0.0
        avg_score = (sum(scores) / len(scores)) if scores else None
        metrics = {
            "total_runs": total,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "avg_score": avg_score,
        }

        metric_row = self._deps.experiment_runs.create_metric(
            experiment_id=experiment_id,
            variant_id=variant_id,
            metrics=metrics,
        )
        metrics["metric_id"] = metric_row.get("id")

        self._deps.experiments.update_experiment(
            experiment_id=experiment_id, client_id=client_id, status="completed"
        )

        return ExperimentRunResult(
            experiment_id=experiment_id,
            variant_id=variant_id,
            runs=runs_payload,
            metrics=metrics,
        )


def _build_variant_product(
    *, product: Dict[str, Any], variant: Dict[str, Any]
) -> tuple[SimulationProduct, Dict[str, Any]]:
    metadata = dict(product.get("metadata") or {})
    variant_payload = variant.get("payload") or {}
    payload_meta = variant_payload.get("metadata")
    if isinstance(payload_meta, dict):
        metadata.update(payload_meta)

    name = variant_payload.get("name") or product.get("name") or "Product"
    description = variant_payload.get("description") or product.get("description") or ""

    raw = {
        "id": product["id"],
        "brand_id": product.get("brand_id"),
        "name": name,
        "description": description,
        "source": str(metadata.get("source") or "catalog"),
        "url": metadata.get("offer_url") or metadata.get("url"),
        "price": metadata.get("price"),
        "confidence": 0.7,
        "metadata": metadata,
    }

    sim = SimulationProduct(
        id=raw["id"],
        name=raw["name"],
        description=raw["description"],
        source=raw["source"],
        url=raw.get("url"),
        price=raw.get("price"),
        confidence=raw.get("confidence") or 0.7,
        metadata=raw.get("metadata") or {},
    )
    return sim, raw


__all__ = ["ExperimentRunner", "ExperimentRunResult"]
