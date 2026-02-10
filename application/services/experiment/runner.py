from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.simulation.service import SimulationService
from application.services.simulation.runner import run_simulation
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
        execution_mode: Literal["simulation", "retrieval_backed"] = "simulation",
        retrieval_max_results: int = 5,
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
        normalized_execution_mode = _normalize_execution_mode(execution_mode)
        retrieval_backed_runs = 0
        retrieval_fallback_runs = 0
        wins = 0
        wins_keyword = 0
        wins_robust = 0
        positive_weight_total = sum(
            _coerce_non_negative_weight(query.get("weight"))
            for query in enabled_queries
        )
        use_weighted_metrics = positive_weight_total > 0
        fallback_weight_total = float(len(enabled_queries)) if enabled_queries else 0.0
        effective_weight_total = (
            positive_weight_total if use_weighted_metrics else fallback_weight_total
        )

        weighted_wins = 0.0
        weighted_wins_keyword = 0.0
        weighted_wins_robust = 0.0
        competitive_weight_total = 0.0
        competitive_runs = 0
        single_candidate_runs = 0
        weighted_score_sum = 0.0
        weighted_score_weight = 0.0
        weighted_score_keyword_sum = 0.0
        weighted_score_keyword_weight = 0.0
        weighted_protocol_readiness_sum = 0.0
        weighted_protocol_readiness_weight = 0.0
        weighted_judge_consensus_wins = 0.0
        weighted_judge_total = 0.0

        for query in enabled_queries:
            query_weight = _resolve_query_weight(
                raw_weight=query.get("weight"),
                use_weighted_metrics=use_weighted_metrics,
            )
            sim_product, raw_product = _build_variant_product(
                product=product, variant=variant
            )
            response, query_execution_mode, retrieval_summary = (
                self._run_query_with_mode(
                    query_text=query["query_text"],
                    sim_product=sim_product,
                    raw_product=raw_product,
                    normalized_execution_mode=normalized_execution_mode,
                    client_id=client_id,
                    user_id=user_id,
                    brand_id=experiment.get("brand_id"),
                    product_id=experiment.get("product_id"),
                    competitor_client_ids=competitor_client_ids,
                    retrieval_max_results=retrieval_max_results,
                )
            )
            run_id = response.get("run_id")
            result = response.get("result") or {}
            winner_id = result.get("winner_id")
            winner_id_keyword = result.get("winner_id_keyword")
            scores = result.get("scores") or []
            if query_execution_mode == "retrieval_backed":
                retrieval_backed_runs += 1
                if retrieval_summary and retrieval_summary.get("fallback_used"):
                    retrieval_fallback_runs += 1
            candidate_count = len(scores) if isinstance(scores, list) else 0
            is_competitive = candidate_count > 1

            score = score_for_product(result.get("scores", []), product["id"])
            score_kw = score_for_product(
                result.get("scores_keyword", []), product["id"]
            )
            if score is not None:
                weighted_score_sum += score * query_weight
                weighted_score_weight += query_weight
            if score_kw is not None:
                weighted_score_keyword_sum += score_kw * query_weight
                weighted_score_keyword_weight += query_weight
            if is_competitive:
                competitive_runs += 1
                competitive_weight_total += query_weight
            else:
                single_candidate_runs += 1

            if is_competitive and winner_id == product["id"]:
                wins += 1
                weighted_wins += query_weight
            if is_competitive and winner_id_keyword == product["id"]:
                wins_keyword += 1
                weighted_wins_keyword += query_weight
            if (
                is_competitive
                and winner_id == product["id"]
                and winner_id_keyword == product["id"]
            ):
                wins_robust += 1
                weighted_wins_robust += query_weight

            readiness_score = _extract_protocol_readiness_score_for_product(
                result, product_id=product["id"]
            )
            if readiness_score is not None:
                weighted_protocol_readiness_sum += readiness_score * query_weight
                weighted_protocol_readiness_weight += query_weight

            judge_results, consensus_winner = _run_pairwise_judges(
                deps=self._deps,
                judge_providers=self._judge_providers,
                query_text=query["query_text"],
                run_id=run_id,
                target_product_id=product["id"],
                scores=result.get("scores") or [],
            )
            if judge_results:
                weighted_judge_total += query_weight
                if consensus_winner == product["id"]:
                    weighted_judge_consensus_wins += query_weight

            self._deps.experiment_runs.create_run(
                experiment_id=experiment_id,
                variant_id=variant_id,
                query_id=query["id"],
                simulation_run_id=run_id,
                execution_mode=query_execution_mode,
                retrieval_summary=retrieval_summary,
            )

            runs_payload.append(
                {
                    "query_id": query["id"],
                    "query_text": query["query_text"],
                    "query_weight": query_weight,
                    "run_id": run_id,
                    "winner_id": winner_id,
                    "winner_id_keyword": winner_id_keyword,
                    "score": score,
                    "score_keyword": score_kw,
                    "candidate_count": candidate_count,
                    "is_competitive": is_competitive,
                    "execution_mode": query_execution_mode,
                    "retrieval_summary": retrieval_summary,
                    "protocol_readiness_score": readiness_score,
                    "judge_results": judge_results,
                    "judge_consensus_winner": consensus_winner,
                }
            )

        total = len(enabled_queries)
        denominator = competitive_weight_total if competitive_weight_total > 0 else 0.0
        win_rate = (weighted_wins / denominator) if denominator else 0.0
        win_rate_keyword = (
            (weighted_wins_keyword / denominator) if denominator else 0.0
        )
        win_rate_robust = (
            (weighted_wins_robust / denominator) if denominator else 0.0
        )
        judge_consensus_win_rate = (
            (weighted_judge_consensus_wins / weighted_judge_total)
            if weighted_judge_total > 0
            else None
        )
        avg_score = (
            weighted_score_sum / weighted_score_weight
            if weighted_score_weight > 0
            else None
        )
        avg_score_keyword = (
            (weighted_score_keyword_sum / weighted_score_keyword_weight)
            if weighted_score_keyword_weight > 0
            else None
        )
        avg_protocol_readiness = (
            (weighted_protocol_readiness_sum / weighted_protocol_readiness_weight)
            if weighted_protocol_readiness_weight > 0
            else None
        )
        metrics = {
            "total_runs": total,
            "competitive_runs": competitive_runs,
            "single_candidate_runs": single_candidate_runs,
            "competitive_coverage": round((competitive_runs / total), 4)
            if total
            else 0.0,
            "total_weight": round(effective_weight_total, 4),
            "competitive_weight_total": round(competitive_weight_total, 4),
            "weights_applied": use_weighted_metrics,
            "wins": wins,
            "weighted_wins": round(weighted_wins, 4),
            "win_rate": round(win_rate, 4),
            "avg_score": avg_score,
            "wins_keyword": wins_keyword,
            "weighted_wins_keyword": round(weighted_wins_keyword, 4),
            "win_rate_keyword": round(win_rate_keyword, 4),
            "wins_robust": wins_robust,
            "weighted_wins_robust": round(weighted_wins_robust, 4),
            "win_rate_robust": round(win_rate_robust, 4),
            "avg_score_keyword": avg_score_keyword,
            "avg_protocol_readiness_score": avg_protocol_readiness,
            "judge_consensus_win_rate": round(judge_consensus_win_rate, 4)
            if judge_consensus_win_rate is not None
            else None,
            "judge_provider_count": len(self._judge_providers),
            "execution_mode": normalized_execution_mode,
            "retrieval_backed_runs": retrieval_backed_runs,
            "retrieval_fallback_runs": retrieval_fallback_runs,
            "retrieval_success_rate": round(
                (retrieval_backed_runs - retrieval_fallback_runs) / retrieval_backed_runs,
                4,
            )
            if retrieval_backed_runs > 0
            else None,
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

    def _run_query_with_mode(
        self,
        *,
        query_text: str,
        sim_product: SimulationProduct,
        raw_product: Dict[str, Any],
        normalized_execution_mode: str,
        client_id: str,
        user_id: Optional[str],
        brand_id: Optional[str],
        product_id: Optional[str],
        competitor_client_ids: Optional[List[str]],
        retrieval_max_results: int,
    ) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
        if normalized_execution_mode != "retrieval_backed":
            response = self._simulation.run(
                query=query_text,
                products=[sim_product],
                client_id=client_id,
                user_id=user_id,
                brand_id=brand_id,
                product_id=product_id,
                raw_products=[raw_product],
                auto_competitors=True,
                competitor_client_ids=competitor_client_ids,
            )
            return response, "simulation", {}
        return self._run_query_retrieval_backed(
            query_text=query_text,
            sim_product=sim_product,
            raw_product=raw_product,
            client_id=client_id,
            user_id=user_id,
            brand_id=brand_id,
            product_id=product_id,
            retrieval_max_results=retrieval_max_results,
        )

    def _run_query_retrieval_backed(
        self,
        *,
        query_text: str,
        sim_product: SimulationProduct,
        raw_product: Dict[str, Any],
        client_id: str,
        user_id: Optional[str],
        brand_id: Optional[str],
        product_id: Optional[str],
        retrieval_max_results: int,
    ) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
        retrieval_summary: Dict[str, Any] = {
            "source": "web_research",
            "fallback_used": False,
            "candidate_count": 0,
        }
        try:
            research = self._deps.run_research(
                query=query_text,
                goals=[query_text],
                context=(
                    "Return candidate products for this exact shopping query. "
                    "Include source URLs and concise snippets."
                ),
                client_id=client_id,
                user_id=user_id,
            )
            retrieval_candidates = _extract_retrieval_candidates(
                research=research, limit=retrieval_max_results
            )
            retrieval_summary["candidate_count"] = len(retrieval_candidates)
            if research and isinstance(research, dict):
                insights = research.get("insights")
                retrieval_summary["insight_count"] = (
                    len(insights) if isinstance(insights, list) else 0
                )
        except Exception as exc:
            retrieval_candidates = []
            retrieval_summary = {
                "source": "web_research",
                "fallback_used": True,
                "candidate_count": 0,
                "error": str(exc),
            }

        if not retrieval_candidates:
            retrieval_summary["source"] = "web_research"
            retrieval_summary["fallback_used"] = False
            retrieval_summary["fallback_reason"] = "no_retrieval_candidates"
            empty_result = _build_empty_retrieval_result(
                query_text=query_text,
                deps=self._deps,
                target_product=sim_product,
            )
            run = self._deps.simulation_runs.create_run(
                query=query_text,
                scenario={
                    "query": query_text,
                    "execution_mode": "retrieval_backed",
                    "retrieval_summary": retrieval_summary,
                },
                products=[raw_product],
                result=empty_result,
                user_id=user_id,
                client_id=client_id,
                brand_id=brand_id,
                product_id=product_id,
            )
            return (
                {"run_id": run.get("id"), "result": empty_result},
                "retrieval_backed",
                retrieval_summary,
            )

        products_for_run: List[SimulationProduct] = [sim_product]
        raw_products_for_run: List[Dict[str, Any]] = [raw_product]
        products_for_run.extend(
            [_to_simulation_product(candidate) for candidate in retrieval_candidates]
        )
        raw_products_for_run.extend(retrieval_candidates)

        result = run_simulation(
            deps=self._deps,
            query=query_text,
            products=products_for_run,
        )
        run = self._deps.simulation_runs.create_run(
            query=query_text,
            scenario={
                "query": query_text,
                "execution_mode": "retrieval_backed",
                "retrieval_summary": retrieval_summary,
            },
            products=raw_products_for_run,
            result=result,
            user_id=user_id,
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
        )
        response = {"run_id": run.get("id"), "result": result}
        return response, "retrieval_backed", retrieval_summary

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


def _normalize_execution_mode(mode: str | None) -> str:
    if (mode or "").strip().lower() == "retrieval_backed":
        return "retrieval_backed"
    return "simulation"


def _extract_retrieval_candidates(
    *, research: Dict[str, Any] | None, limit: int
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    insights = []
    tool_outputs = []
    if isinstance(research, dict):
        raw_insights = research.get("insights")
        if isinstance(raw_insights, list):
            insights = [item for item in raw_insights if isinstance(item, dict)]
        raw_tool_outputs = research.get("tool_outputs")
        if isinstance(raw_tool_outputs, list):
            tool_outputs = [item for item in raw_tool_outputs if isinstance(item, dict)]

    def _append_candidate(
        *,
        name: Any,
        description: Any,
        url: Any,
        source: Any,
        price: Any = None,
    ) -> None:
        name_val = str(name or "").strip()
        if not name_val:
            return
        desc_val = str(description or name_val).strip()
        url_val = str(url or "").strip() or None
        source_val = str(source or "retrieval").strip() or "retrieval"
        key = (url_val or f"{name_val}:{desc_val}")[:256]
        candidate_id = f"retrieval-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"
        if candidate_id in seen:
            return
        seen.add(candidate_id)
        candidates.append(
            {
                "id": candidate_id,
                "brand_id": None,
                "name": name_val,
                "description": desc_val,
                "source": "retrieval",
                "url": url_val,
                "price": _safe_optional_float(price),
                "confidence": 0.55,
                "metadata": {
                    "retrieval_source": source_val,
                    "source_url": url_val,
                },
            }
        )

    for insight in insights:
        _append_candidate(
            name=insight.get("title") or insight.get("name"),
            description=insight.get("summary"),
            url=insight.get("url") or insight.get("source_url"),
            source=insight.get("source"),
            price=insight.get("price"),
        )
        if len(candidates) >= limit:
            return candidates[:limit]

    for output in tool_outputs:
        source_name = output.get("name") or "retrieval_tool"
        payload = output.get("output")
        if not isinstance(payload, dict):
            continue
        results = payload.get("results")
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            _append_candidate(
                name=item.get("name") or item.get("title"),
                description=item.get("snippet") or item.get("summary"),
                url=item.get("url"),
                source=source_name,
                price=item.get("price"),
            )
            if len(candidates) >= limit:
                return candidates[:limit]

    return candidates[:limit]


def _to_simulation_product(raw: Dict[str, Any]) -> SimulationProduct:
    return SimulationProduct(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or "Retrieved product"),
        description=str(raw.get("description") or ""),
        source=str(raw.get("source") or "retrieval"),
        url=raw.get("url"),
        price=_safe_optional_float(raw.get("price")),
        confidence=float(raw.get("confidence") or 0.55),
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
    )


def _build_empty_retrieval_result(
    *, query_text: str, deps: AppDeps, target_product: SimulationProduct
) -> Dict[str, Any]:
    intent = deps.classify_intent(query_text)
    return {
        "intent": intent,
        "goals": [query_text],
        "scores": [],
        "winner_id": None,
        "scores_keyword": [],
        "winner_id_keyword": None,
        "gap_analysis": [],
        "profiles": [],
        "lessons": [
            "No retrieval candidates were returned for this query in retrieval-backed mode."
        ],
        "tone": {"summary": None},
        "metadata": {"target_product_id": target_product.id},
    }


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


def _coerce_non_negative_weight(raw_weight: Any) -> float:
    try:
        weight = float(raw_weight)
    except (TypeError, ValueError):
        return 0.0
    return max(weight, 0.0)


def _resolve_query_weight(*, raw_weight: Any, use_weighted_metrics: bool) -> float:
    if not use_weighted_metrics:
        return 1.0
    return _coerce_non_negative_weight(raw_weight)


def _safe_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
