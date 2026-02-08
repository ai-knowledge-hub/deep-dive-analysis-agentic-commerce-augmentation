from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.simulation.service import SimulationService
from application.services.experiment.brand_belief_service import BrandBeliefService
from application.services.experiment.belief_update_agent import BeliefUpdateAgent
from application.services.experiment.pairwise_judge import judge_pairwise
from domain.simulation.ranking import score_for_product
from domain.simulation.types import SimulationProduct
from shared.config.env import settings


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
        self._beliefs = BrandBeliefService(repo=deps.brand_beliefs)
        self._belief_agent = BeliefUpdateAgent()
        self._judge_providers = _parse_judge_providers()

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
        scores_keyword: List[float] = []
        protocol_readiness_scores: List[int] = []
        wins = 0
        wins_keyword = 0
        wins_robust = 0
        judge_consensus_wins = 0
        judge_runs = 0

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
            winner_id_keyword = result.get("winner_id_keyword")

            score = score_for_product(result.get("scores", []), product["id"])
            score_kw = score_for_product(
                result.get("scores_keyword", []), product["id"]
            )
            if score is not None:
                scores.append(score)
            if score_kw is not None:
                scores_keyword.append(score_kw)
            if winner_id == product["id"]:
                wins += 1
            if winner_id_keyword == product["id"]:
                wins_keyword += 1
            if winner_id == product["id"] and winner_id_keyword == product["id"]:
                wins_robust += 1

            readiness_score = _extract_protocol_readiness_score_for_product(
                result, product_id=product["id"]
            )
            if readiness_score is not None:
                protocol_readiness_scores.append(readiness_score)

            judge_results, consensus_winner = _run_pairwise_judges(
                deps=self._deps,
                judge_providers=self._judge_providers,
                query_text=query["query_text"],
                run_id=run_id,
                target_product_id=product["id"],
                scores=result.get("scores") or [],
            )
            if judge_results:
                judge_runs += 1
                if consensus_winner == product["id"]:
                    judge_consensus_wins += 1

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
                    "winner_id_keyword": winner_id_keyword,
                    "score": score,
                    "score_keyword": score_kw,
                    "protocol_readiness_score": readiness_score,
                    "judge_results": judge_results,
                    "judge_consensus_winner": consensus_winner,
                }
            )

        total = len(enabled_queries)
        win_rate = (wins / total) if total else 0.0
        win_rate_keyword = (wins_keyword / total) if total else 0.0
        win_rate_robust = (wins_robust / total) if total else 0.0
        judge_consensus_win_rate = (
            (judge_consensus_wins / judge_runs) if judge_runs else None
        )
        avg_score = (sum(scores) / len(scores)) if scores else None
        avg_score_keyword = (
            (sum(scores_keyword) / len(scores_keyword)) if scores_keyword else None
        )
        avg_protocol_readiness = (
            (sum(protocol_readiness_scores) / len(protocol_readiness_scores))
            if protocol_readiness_scores
            else None
        )
        metrics = {
            "total_runs": total,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "avg_score": avg_score,
            "wins_keyword": wins_keyword,
            "win_rate_keyword": round(win_rate_keyword, 4),
            "wins_robust": wins_robust,
            "win_rate_robust": round(win_rate_robust, 4),
            "avg_score_keyword": avg_score_keyword,
            "avg_protocol_readiness_score": avg_protocol_readiness,
            "judge_consensus_win_rate": round(judge_consensus_win_rate, 4)
            if judge_consensus_win_rate is not None
            else None,
            "judge_provider_count": len(self._judge_providers),
        }

        metric_row = self._deps.experiment_runs.create_metric(
            experiment_id=experiment_id,
            variant_id=variant_id,
            metrics=metrics,
        )
        metrics["metric_id"] = metric_row.get("id")

        if experiment.get("brand_id"):
            self._record_belief(
                experiment=experiment,
                variant=variant,
                metrics=metrics,
                queries=enabled_queries,
                runs=runs_payload,
                product=product,
                client_id=client_id,
            )

        self._deps.experiments.update_experiment(
            experiment_id=experiment_id, client_id=client_id, status="completed"
        )

        return ExperimentRunResult(
            experiment_id=experiment_id,
            variant_id=variant_id,
            runs=runs_payload,
            metrics=metrics,
        )

    def _record_belief(
        self,
        *,
        experiment: Dict[str, Any],
        variant: Dict[str, Any],
        metrics: Dict[str, Any],
        queries: List[Dict[str, Any]],
        runs: List[Dict[str, Any]],
        product: Dict[str, Any],
        client_id: str,
    ) -> None:
        brand_id = experiment.get("brand_id")
        if not brand_id:
            return
        update = self._belief_agent.build_update(
            experiment=experiment, variant=variant, metrics=metrics
        )
        self._beliefs.create_belief(
            client_id=client_id,
            brand_id=brand_id,
            product_id=experiment.get("product_id"),
            hypothesis=experiment.get("hypothesis") or {},
            evidence={
                "win_rate": metrics.get("win_rate"),
                "avg_score": metrics.get("avg_score"),
                "wins": metrics.get("wins"),
                "total_runs": metrics.get("total_runs"),
                "query_count": len(queries),
                "query_ids": [q.get("id") for q in queries],
                "queries": [
                    {"id": q.get("id"), "text": q.get("query_text")} for q in queries
                ],
                "runs": runs,
                "experiment_id": experiment.get("id"),
                "variant_id": variant.get("id"),
                "winner_product_id": product.get("id"),
                "metric_id": metrics.get("metric_id"),
            },
            recommendation=update.recommendation,
            confidence=update.confidence,
            metadata={
                "experiment_name": experiment.get("name"),
                "variant_label": variant.get("label"),
                "variant_type": variant.get("type"),
                **update.metadata,
            },
        )

    def run_experiment_for_all_variants(
        self,
        *,
        experiment_id: str,
        client_id: str,
        user_id: Optional[str] = None,
    ) -> List[ExperimentRunResult]:
        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        if not variants:
            raise ValueError("experiment has no variants")
        results: List[ExperimentRunResult] = []
        for variant in variants:
            results.append(
                self.run_experiment(
                    experiment_id=experiment_id,
                    variant_id=variant["id"],
                    client_id=client_id,
                    user_id=user_id,
                )
            )
        return results


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
        "source": str(metadata.get("source") or "product"),
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


def _extract_protocol_readiness_score_for_product(
    result: Dict[str, Any], *, product_id: str
) -> Optional[int]:
    """Best-effort parse of protocol readiness score from simulation results."""
    readiness = result.get("protocol_readiness")
    if not isinstance(readiness, list):
        return None
    for preferred_protocol in ("ucp", "acp"):
        entry = next(
            (
                item
                for item in readiness
                if item.get("product_id") == product_id
                and item.get("protocol") == preferred_protocol
            ),
            None,
        )
        if not isinstance(entry, dict):
            continue
        issues = entry.get("issues") or []
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            field = issue.get("field")
            if field not in {"ucp_readiness_score", "acp_readiness_score"}:
                continue
            message = issue.get("message") or ""
            if not isinstance(message, str):
                continue
            import re

            match = re.search(r"(\\d{1,3})\\s*/\\s*100", message)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return None
    return None


def _parse_judge_providers() -> List[str]:
    raw = getattr(settings, "judge_providers", "") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _run_pairwise_judges(
    *,
    deps: AppDeps,
    judge_providers: List[str],
    query_text: str,
    run_id: Optional[str],
    target_product_id: str,
    scores: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    if not judge_providers or not run_id:
        return [], None
    run_record = deps.simulation_runs.get_run(run_id)
    if not run_record:
        return [], None
    products = run_record.get("products") or []
    target = next((p for p in products if p.get("id") == target_product_id), None)
    if not target:
        return [], None
    competitor_id = _best_competitor_id(scores, target_product_id)
    if not competitor_id:
        return [], None
    competitor = next((p for p in products if p.get("id") == competitor_id), None)
    if not competitor:
        return [], None

    results: List[Dict[str, Any]] = []
    for provider in judge_providers:
        try:
            result = judge_pairwise(
                query=query_text,
                product_a=target,
                product_b=competitor,
                generate_fn=deps.generate_with_provider,
                provider=provider,
            )
            winner = result.get("winner")
            winner_id = (
                target_product_id
                if winner == "a"
                else competitor_id
                if winner == "b"
                else None
            )
            results.append(
                {
                    "provider": provider,
                    "winner_id": winner_id,
                    "raw": result.get("raw"),
                }
            )
        except Exception:
            results.append(
                {
                    "provider": provider,
                    "winner_id": None,
                    "raw": None,
                }
            )

    consensus = _consensus_winner(results)
    return results, consensus


def _best_competitor_id(
    scores: List[Dict[str, Any]], target_product_id: str
) -> Optional[str]:
    best_id = None
    best_score = None
    for item in scores:
        pid = item.get("product_id")
        if not pid or pid == target_product_id:
            continue
        try:
            score_val = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            score_val = 0.0
        if best_score is None or score_val > best_score:
            best_score = score_val
            best_id = pid
    return best_id


def _consensus_winner(results: List[Dict[str, Any]]) -> Optional[str]:
    votes: Dict[str, int] = {}
    for item in results:
        winner_id = item.get("winner_id")
        if not winner_id:
            continue
        votes[winner_id] = votes.get(winner_id, 0) + 1
    if not votes:
        return None
    sorted_votes = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)
    top_id, top_count = sorted_votes[0]
    if len(sorted_votes) > 1 and sorted_votes[1][1] == top_count:
        return None
    return top_id


__all__ = ["ExperimentRunner", "ExperimentRunResult"]
