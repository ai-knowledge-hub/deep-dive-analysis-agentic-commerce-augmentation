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
from application.services.experiment.decision_policy import (
    DecisionInputs,
    EvidenceSignal,
    as_audit_payload,
    decide,
)
from application.services.experiment.pairwise_judge import judge_pairwise
from application.services.loop.belief_update_service import BeliefUpdateService, clamp
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
        self._belief_updates = BeliefUpdateService(deps=deps)
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
        frozen_snapshot_version: Optional[int] = None
        retrieval_candidates_by_query: Dict[str, List[Dict[str, Any]]] = {}
        if normalized_execution_mode == "retrieval_backed":
            (
                frozen_snapshot_version,
                retrieval_candidates_by_query,
            ) = self._ensure_frozen_retrieval_snapshots(
                experiment=experiment,
                enabled_queries=enabled_queries,
                client_id=client_id,
                user_id=user_id,
                retrieval_max_results=retrieval_max_results,
            )
            if not _is_control_variant(variant):
                if not self._has_control_baseline_for_snapshot(
                    experiment_id=experiment_id,
                    snapshot_version=frozen_snapshot_version,
                ):
                    raise ValueError(
                        "Baseline not scored yet for current frozen retrieval snapshot. "
                        "Run the control variant first."
                    )
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
                    query_id=query["id"],
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
                    retrieval_candidates_override=retrieval_candidates_by_query.get(
                        query.get("id"), []
                    ),
                    snapshot_version=frozen_snapshot_version,
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
                snapshot_version=frozen_snapshot_version,
                hypothesis_id=variant.get("hypothesis_id"),
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
                    "snapshot_version": frozen_snapshot_version,
                    "hypothesis_id": variant.get("hypothesis_id"),
                    "protocol_readiness_score": readiness_score,
                    "judge_results": judge_results,
                    "judge_consensus_winner": consensus_winner,
                }
            )

        total = len(enabled_queries)
        denominator = competitive_weight_total if competitive_weight_total > 0 else 0.0
        win_rate = (weighted_wins / denominator) if denominator else 0.0
        win_rate_keyword = (weighted_wins_keyword / denominator) if denominator else 0.0
        win_rate_robust = (weighted_wins_robust / denominator) if denominator else 0.0
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
                (retrieval_backed_runs - retrieval_fallback_runs)
                / retrieval_backed_runs,
                4,
            )
            if retrieval_backed_runs > 0
            else None,
            "snapshot_version": frozen_snapshot_version,
        }

        if normalized_execution_mode == "retrieval_backed" and _is_control_variant(
            variant
        ):
            self._seed_hypotheses_from_baseline(
                experiment=experiment,
                runs=runs_payload,
                snapshot_version=frozen_snapshot_version or 0,
            )

        if (
            normalized_execution_mode == "retrieval_backed"
            and not _is_control_variant(variant)
            and experiment.get("brand_id")
        ):
            baseline_win_rate = self._get_baseline_win_rate_for_snapshot(
                experiment=experiment,
                snapshot_version=frozen_snapshot_version or 0,
            )
            if baseline_win_rate is not None:
                metrics["baseline_win_rate"] = round(float(baseline_win_rate), 4)
                metrics["win_rate_lift"] = round(
                    float(metrics.get("win_rate") or 0.0) - float(baseline_win_rate), 4
                )

            posterior = self._update_variant_posterior(
                experiment=experiment,
                variant=variant,
                metrics=metrics,
                client_id=client_id,
            )
            if posterior is not None:
                metrics["posterior"] = round(posterior, 4)

            decision_inputs, decision_outputs = self._build_and_apply_decision_policy(
                experiment=experiment,
                variant=variant,
                enabled_queries=enabled_queries,
                metrics=metrics,
                client_id=client_id,
            )
            metrics["decision_action"] = decision_outputs.get("action")
            metrics["decision_policy_version"] = decision_outputs.get("policy_version")
            metrics["decision_inputs"] = decision_inputs
            metrics["decision_outputs"] = decision_outputs

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

    def _ensure_frozen_retrieval_snapshots(
        self,
        *,
        experiment: Dict[str, Any],
        enabled_queries: List[Dict[str, Any]],
        client_id: str,
        user_id: Optional[str],
        retrieval_max_results: int,
    ) -> tuple[int, Dict[str, List[Dict[str, Any]]]]:
        experiment_id = str(experiment.get("id") or "")
        battery_id = str(experiment.get("battery_id") or "")
        if not experiment_id or not battery_id:
            return 0, {}
        current_version = int(experiment.get("protocol_snapshot_version") or 0)
        expected_query_ids = {str(item.get("id") or "") for item in enabled_queries}
        if current_version > 0:
            existing_rows = self._deps.experiment_retrieval_snapshots.list_snapshots(
                experiment_id=experiment_id,
                snapshot_version=current_version,
                limit=max(2000, len(expected_query_ids) * 3),
            )
            existing_query_ids = {
                str(row.get("query_id") or "")
                for row in existing_rows
                if row.get("query_id")
            }
            if expected_query_ids.issubset(existing_query_ids):
                return current_version, self._load_snapshot_candidates(
                    experiment_id=experiment_id,
                    snapshot_version=current_version,
                    enabled_queries=enabled_queries,
                )

        next_version = (
            max(
                current_version,
                int(
                    self._deps.experiment_retrieval_snapshots.latest_snapshot_version(
                        experiment_id=experiment_id
                    )
                    or 0
                ),
            )
            + 1
        )

        candidates_by_query: Dict[str, List[Dict[str, Any]]] = {}
        for query in enabled_queries:
            query_text = str(query.get("query_text") or "")
            query_id = str(query.get("id") or "")
            retrieval_payload = _build_retrieval_payload(
                query_text=query_text,
                research=self._safe_run_research(
                    query_text=query_text,
                    client_id=client_id,
                    user_id=user_id,
                ),
                retrieval_max_results=retrieval_max_results,
            )
            self._deps.experiment_retrieval_snapshots.create_snapshot(
                experiment_id=experiment_id,
                battery_id=battery_id,
                query_id=query_id,
                snapshot_version=next_version,
                retrieval=retrieval_payload,
            )
            candidates_by_query[query_id] = retrieval_payload.get("candidates") or []

        self._deps.experiments.update_experiment(
            experiment_id=experiment_id,
            client_id=client_id,
            competitor_policy={
                **(experiment.get("competitor_policy") or {}),
                "protocol": {"frozen": True, "snapshot_version": next_version},
            },
            protocol_snapshot_version=next_version,
        )
        return next_version, candidates_by_query

    def _load_snapshot_candidates(
        self,
        *,
        experiment_id: str,
        snapshot_version: int,
        enabled_queries: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        query_ids = {str(item.get("id") or "") for item in enabled_queries}
        rows = self._deps.experiment_retrieval_snapshots.list_snapshots(
            experiment_id=experiment_id,
            snapshot_version=snapshot_version,
            limit=max(2000, len(query_ids) * 3),
        )
        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            query_id = str(row.get("query_id") or "")
            if query_id not in query_ids or query_id in result:
                continue
            retrieval = row.get("retrieval") or {}
            candidates = retrieval.get("candidates")
            if isinstance(candidates, list):
                result[query_id] = [
                    item for item in candidates if isinstance(item, dict)
                ]
            else:
                result[query_id] = []
        for query_id in query_ids:
            result.setdefault(query_id, [])
        return result

    def _safe_run_research(
        self,
        *,
        query_text: str,
        client_id: str,
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        try:
            return self._deps.run_research(
                query=query_text,
                goals=[query_text],
                context=(
                    "Return candidate products for this exact shopping query. "
                    "Include source URLs and concise snippets."
                ),
                client_id=client_id,
                user_id=user_id,
            )
        except Exception:
            return {}

    def _has_control_baseline_for_snapshot(
        self, *, experiment_id: str, snapshot_version: Optional[int]
    ) -> bool:
        if snapshot_version is None:
            return False
        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        control_ids = {
            str(item.get("id") or "") for item in variants if _is_control_variant(item)
        }
        if not control_ids:
            return False
        metrics = self._deps.experiment_runs.list_metrics(
            experiment_id=experiment_id, limit=500
        )
        for metric in metrics:
            if str(metric.get("variant_id") or "") not in control_ids:
                continue
            payload = metric.get("metrics") or {}
            if int(payload.get("snapshot_version") or 0) == int(snapshot_version):
                return True
        return False

    def _seed_hypotheses_from_baseline(
        self,
        *,
        experiment: Dict[str, Any],
        runs: List[Dict[str, Any]],
        snapshot_version: int,
    ) -> None:
        experiment_id = str(experiment.get("id") or "")
        if not experiment_id or snapshot_version <= 0:
            return
        existing = self._deps.experiment_hypotheses.count_hypotheses(
            experiment_id=experiment_id,
            snapshot_version=snapshot_version,
        )
        if existing > 0:
            return
        signal_counts: Dict[str, int] = {}
        for row in runs:
            run_id = row.get("run_id")
            if not run_id:
                continue
            sim_run = self._deps.simulation_runs.get_run(run_id)
            gap_analysis = ((sim_run or {}).get("result") or {}).get(
                "gap_analysis"
            ) or []
            if not isinstance(gap_analysis, list):
                continue
            target = next(
                (
                    item
                    for item in gap_analysis
                    if item.get("product_id") == experiment.get("product_id")
                ),
                gap_analysis[0] if gap_analysis else None,
            )
            for signal in (target or {}).get("missing_signals") or []:
                key = str(signal or "").strip()
                if not key:
                    continue
                signal_counts[key] = signal_counts.get(key, 0) + 1

        top_signals = [
            signal
            for signal, _count in sorted(
                signal_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:4]
        ]
        if not top_signals:
            return
        for signal in top_signals:
            self._deps.experiment_hypotheses.create_hypothesis(
                experiment_id=experiment_id,
                snapshot_version=snapshot_version,
                source="retrieval_gap",
                statement={
                    "if": f"add or strengthen signal '{signal}'",
                    "then": "rank-fit and comparative score improve",
                    "for": "queries where this signal appears in winners",
                },
            )

    def _update_variant_posterior(
        self,
        *,
        experiment: Dict[str, Any],
        variant: Dict[str, Any],
        metrics: Dict[str, Any],
        client_id: str,
    ) -> Optional[float]:
        hypothesis_id = (
            str(variant.get("hypothesis_id") or "").strip()
            or str(variant.get("id") or "").strip()
        )
        if not hypothesis_id:
            return None
        evidence = {
            "source": "synthetic",
            "provider": "experiment_runner",
            "score": float(metrics.get("win_rate") or 0.0),
            "confidence": float(metrics.get("judge_consensus_win_rate") or 0.5),
            "support_size": int(metrics.get("competitive_runs") or 1),
            "experiment_id": experiment.get("id"),
            "variant_id": variant.get("id"),
            "snapshot_version": metrics.get("snapshot_version"),
        }
        revision = self._belief_updates.update(
            client_id=client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            hypothesis_key=f"experiment_hypothesis:{hypothesis_id}",
            evidence=evidence,
        )
        posterior = revision.get("posterior")
        try:
            return float(posterior)
        except (TypeError, ValueError):
            return None

    def _get_baseline_win_rate_for_snapshot(
        self, *, experiment: Dict[str, Any], snapshot_version: int
    ) -> float | None:
        experiment_id = str(experiment.get("id") or "")
        if not experiment_id:
            return None
        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        control = next((v for v in variants if _is_control_variant(v)), None)
        if not control:
            return None
        control_metrics = self._deps.experiment_runs.list_metrics(
            experiment_id=experiment_id,
            variant_id=str(control.get("id") or ""),
            limit=50,
        )
        for row in control_metrics:
            m = row.get("metrics") or {}
            if int(m.get("snapshot_version") or -1) != int(snapshot_version):
                continue
            if str(m.get("execution_mode") or "") != "retrieval_backed":
                continue
            try:
                return float(m.get("win_rate"))
            except (TypeError, ValueError):
                continue
        return None

    def _build_and_apply_decision_policy(
        self,
        *,
        experiment: Dict[str, Any],
        variant: Dict[str, Any],
        enabled_queries: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        client_id: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        # Experiment signal: use lift if available, otherwise fall back to raw win_rate centered at 0.5.
        win_rate = _safe_optional_float(metrics.get("win_rate"))
        baseline_win_rate = _safe_optional_float(metrics.get("baseline_win_rate"))
        if baseline_win_rate is None:
            baseline_win_rate = 0.5
        exp_effect = _safe_optional_float(metrics.get("win_rate_lift"))
        if exp_effect is None and win_rate is not None:
            exp_effect = win_rate - baseline_win_rate
        exp_effect = max(-1.0, min(1.0, float(exp_effect or 0.0)))

        consensus = _safe_optional_float(metrics.get("judge_consensus_win_rate"))
        total_runs = int(metrics.get("total_runs") or 0)
        competitive_coverage = (
            _safe_optional_float(metrics.get("competitive_coverage")) or 0.0
        )
        r_exp = clamp(
            ((consensus if consensus is not None else 0.5) * 0.4)
            + (min(1.0, total_runs / 10.0) * 0.3)
            + (competitive_coverage * 0.3)
        )

        # Observed signal: manual validations linked to this variant (best-effort today).
        validations = self._deps.experiment_validations.list_validations(
            experiment_id=str(experiment.get("id") or ""), limit=200
        )
        variant_id = str(variant.get("id") or "")
        v_validations = [
            v for v in validations if str(v.get("variant_id") or "") == variant_id
        ]
        verified = [v for v in v_validations if v.get("is_correct") is not None]
        correct = [v for v in verified if v.get("is_correct") is True]
        verified_runs = len(verified)
        correct_runs = len(correct)
        obs_accuracy = (correct_runs / verified_runs) if verified_runs else None
        obs_effect = (
            None
            if obs_accuracy is None
            else max(-1.0, min(1.0, (obs_accuracy * 2.0) - 1.0))
        )
        r_obs = clamp(min(1.0, verified_runs / 10.0)) if verified_runs else 0.0

        distinct_q = {
            str(v.get("query_text") or "").strip().lower()
            for v in verified
            if str(v.get("query_text") or "").strip()
        }
        coverage_obs = (
            (len(distinct_q) / len(enabled_queries)) if enabled_queries else 0.0
        )

        # Synthetic validation signal (Validation jobs/results linked to this experiment id).
        syn_effect = None
        syn_reliability = 0.0
        syn_support = 0
        try:
            variants = self._deps.experiments.list_variants(
                experiment_id=str(experiment.get("id") or "")
            )
            control = next((v for v in variants if _is_control_variant(v)), None)
            control_id = str((control or {}).get("id") or "")
            jobs = self._deps.validation_jobs.list_jobs(
                client_id=client_id,
                entity_type="experiment_run",
                entity_id=str(experiment.get("id") or ""),
                limit=200,
            )
            scored: List[tuple[float, float]] = []
            provider_counts: Dict[str, int] = {}
            for job in jobs:
                if str(job.get("status") or "").lower() != "completed":
                    continue
                provider_counts[str(job.get("provider") or "unknown")] = (
                    provider_counts.get(str(job.get("provider") or "unknown"), 0) + 1
                )
                result = self._deps.validation_results.get_latest_for_job(
                    job_id=str(job.get("id") or "")
                )
                if not result:
                    continue
                structured = result.get("structured_result") or {}
                winner_raw = str(
                    result.get("winner_id") or structured.get("winner_id") or ""
                ).strip()
                winner_id = _resolve_validation_winner_variant_id(
                    winner_raw=winner_raw,
                    job_input_payload=job.get("input_payload") or {},
                    current_variant_id=str(variant.get("id") or ""),
                    control_variant_id=control_id,
                )
                score = _safe_optional_float(result.get("score"))
                if score is None:
                    score = _safe_optional_float(structured.get("score"))
                confidence = _safe_optional_float(structured.get("confidence"))
                evidence_strength = str(
                    result.get("evidence_strength")
                    or structured.get("evidence_strength")
                    or ""
                ).lower()

                # If the judge doesn't pick a known winner, skip the datapoint (non-informative).
                if not winner_id:
                    continue
                if winner_id not in {str(variant.get("id") or ""), control_id}:
                    continue

                if score is None:
                    # Treat unknown score as weak signal.
                    score = 0.5
                score = clamp(float(score))
                base = (score * 2.0) - 1.0  # [-1, +1]
                effect_i = base if winner_id == str(variant.get("id") or "") else -base

                strength_map = {"weak": 0.3, "moderate": 0.6, "strong": 0.9}
                strength = float(strength_map.get(evidence_strength, 0.5))
                conf = clamp(float(confidence) if confidence is not None else 0.5)
                r_i = clamp((conf * 0.6) + (strength * 0.4))
                scored.append((effect_i, r_i))

            syn_support = len(scored)
            if syn_support:
                # Reliability-weighted mean effect.
                denom = sum(r for _e, r in scored) or 1.0
                syn_effect = sum(e * r for e, r in scored) / denom
                syn_effect = max(-1.0, min(1.0, float(syn_effect)))
                # Aggregate reliability scales with sample size.
                mean_r = sum(r for _e, r in scored) / float(syn_support)
                syn_reliability = clamp(mean_r * min(1.0, syn_support / 10.0))
                metrics["synthetic_validation_summary"] = {
                    "jobs_considered": len(jobs),
                    "results_scored": syn_support,
                    "providers": provider_counts,
                }
        except Exception:
            # Synthetic validation is optional; decisioning will still work with experiment+observed.
            syn_effect = None
            syn_reliability = 0.0
            syn_support = 0

        inputs = DecisionInputs(
            exp=EvidenceSignal(
                effect=exp_effect,
                reliability=r_exp,
                support_size=total_runs,
                details={
                    "win_rate": win_rate,
                    "baseline_win_rate": baseline_win_rate,
                    "win_rate_lift": exp_effect,
                    "judge_consensus_win_rate": consensus,
                    "competitive_coverage": competitive_coverage,
                    "total_runs": total_runs,
                },
            ),
            syn=EvidenceSignal(
                effect=syn_effect,
                reliability=syn_reliability,
                support_size=syn_support or None,
                details={
                    "support_size": syn_support,
                }
                if syn_support
                else None,
            ),
            obs=EvidenceSignal(
                effect=obs_effect,
                reliability=r_obs,
                support_size=verified_runs,
                details={
                    "verified_runs": verified_runs,
                    "correct_runs": correct_runs,
                    "accuracy": obs_accuracy,
                },
            ),
            coverage_obs=coverage_obs,
        )
        outputs = decide(inputs)
        inputs_payload, outputs_payload = as_audit_payload(
            inputs=inputs, outputs=outputs
        )
        return inputs_payload, outputs_payload

    def _run_query_with_mode(
        self,
        *,
        query_id: str,
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
        retrieval_candidates_override: Optional[List[Dict[str, Any]]] = None,
        snapshot_version: Optional[int] = None,
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
            query_id=query_id,
            query_text=query_text,
            sim_product=sim_product,
            raw_product=raw_product,
            client_id=client_id,
            user_id=user_id,
            brand_id=brand_id,
            product_id=product_id,
            retrieval_max_results=retrieval_max_results,
            retrieval_candidates_override=retrieval_candidates_override,
            snapshot_version=snapshot_version,
        )

    def _run_query_retrieval_backed(
        self,
        *,
        query_id: str,
        query_text: str,
        sim_product: SimulationProduct,
        raw_product: Dict[str, Any],
        client_id: str,
        user_id: Optional[str],
        brand_id: Optional[str],
        product_id: Optional[str],
        retrieval_max_results: int,
        retrieval_candidates_override: Optional[List[Dict[str, Any]]] = None,
        snapshot_version: Optional[int] = None,
    ) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
        retrieval_summary: Dict[str, Any] = {
            "source": "web_research",
            "fallback_used": False,
            "candidate_count": 0,
        }
        if retrieval_candidates_override is not None:
            retrieval_candidates = [
                item for item in retrieval_candidates_override if isinstance(item, dict)
            ][:retrieval_max_results]
            retrieval_summary["source"] = "frozen_snapshot"
            retrieval_summary["candidate_count"] = len(retrieval_candidates)
            retrieval_summary["query_id"] = query_id
            retrieval_summary["snapshot_version"] = snapshot_version
        else:
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

    def freeze_retrieval_protocol(
        self,
        *,
        experiment_id: str,
        client_id: str,
        user_id: Optional[str] = None,
        retrieval_max_results: int = 5,
    ) -> Dict[str, Any]:
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")
        battery_id = experiment.get("battery_id")
        if not battery_id:
            raise ValueError("experiment missing battery_id")
        queries = self._deps.query_batteries.list_queries(battery_id=battery_id)
        enabled_queries = [q for q in queries if q.get("enabled")]
        if not enabled_queries:
            raise ValueError("battery has no enabled queries")

        snapshot_version, candidates = self._ensure_frozen_retrieval_snapshots(
            experiment=experiment,
            enabled_queries=enabled_queries,
            client_id=client_id,
            user_id=user_id,
            retrieval_max_results=retrieval_max_results,
        )
        return {
            "experiment_id": experiment_id,
            "snapshot_version": snapshot_version,
            "query_count": len(enabled_queries),
            "retrieval_candidates_by_query_count": len(candidates),
            "status": "frozen",
        }

    def seed_hypotheses_for_snapshot(
        self,
        *,
        experiment_id: str,
        client_id: str,
        snapshot_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")
        target_snapshot_version = int(
            snapshot_version
            if snapshot_version is not None
            else (experiment.get("protocol_snapshot_version") or 0)
        )
        if target_snapshot_version <= 0:
            raise ValueError(
                "seed_hypotheses requires a frozen snapshot_version (run freeze first)"
            )
        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        control_ids = {
            str(v.get("id") or "") for v in variants if _is_control_variant(v)
        }
        if not control_ids:
            raise ValueError("seed_hypotheses requires a control variant")
        runs = self._deps.experiment_runs.list_runs(
            experiment_id=experiment_id, limit=5000
        )
        baseline_runs = [
            {
                "run_id": run.get("simulation_run_id"),
                "snapshot_version": run.get("snapshot_version"),
            }
            for run in runs
            if str(run.get("variant_id") or "") in control_ids
            and int(run.get("snapshot_version") or 0) == target_snapshot_version
            and run.get("simulation_run_id")
        ]
        if not baseline_runs:
            raise ValueError(
                "seed_hypotheses requires baseline runs for the target snapshot_version"
            )
        before = self._deps.experiment_hypotheses.count_hypotheses(
            experiment_id=experiment_id,
            snapshot_version=target_snapshot_version,
        )
        self._seed_hypotheses_from_baseline(
            experiment=experiment,
            runs=baseline_runs,
            snapshot_version=target_snapshot_version,
        )
        after = self._deps.experiment_hypotheses.count_hypotheses(
            experiment_id=experiment_id,
            snapshot_version=target_snapshot_version,
        )
        return {
            "experiment_id": experiment_id,
            "snapshot_version": target_snapshot_version,
            "baseline_runs_count": len(baseline_runs),
            "hypotheses_before": before,
            "hypotheses_after": after,
            "created_count": max(0, after - before),
            "status": "seeded",
        }

    def update_posterior_and_decisions(
        self,
        *,
        experiment_id: str,
        client_id: str,
        variant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")
        battery_id = experiment.get("battery_id")
        if not battery_id:
            raise ValueError("experiment missing battery_id")
        queries = self._deps.query_batteries.list_queries(battery_id=battery_id)
        enabled_queries = [q for q in queries if q.get("enabled")]
        if not enabled_queries:
            raise ValueError("battery has no enabled queries")

        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        variant_map = {str(v.get("id") or ""): v for v in variants}

        selected_variant: Dict[str, Any] | None = None
        if variant_id:
            selected_variant = variant_map.get(str(variant_id))
            if not selected_variant:
                raise ValueError("variant not found for experiment")
        else:
            for item in variants:
                if _is_control_variant(item):
                    continue
                selected_variant = item
                break
        if not selected_variant:
            raise ValueError("no candidate variant found")
        if _is_control_variant(selected_variant):
            raise ValueError(
                "update_posterior_and_decisions requires candidate variant"
            )

        selected_variant_id = str(selected_variant.get("id") or "")
        metric_rows = self._deps.experiment_runs.list_metrics(
            experiment_id=experiment_id,
            variant_id=selected_variant_id,
            limit=50,
        )
        latest_metric = None
        for row in metric_rows:
            payload = row.get("metrics") or {}
            if str(payload.get("execution_mode") or "") == "retrieval_backed":
                latest_metric = row
                break
        if not latest_metric:
            raise ValueError(
                "no retrieval-backed metric found for variant; run variant first"
            )

        metrics = dict((latest_metric.get("metrics") or {}))
        snapshot_version = int(metrics.get("snapshot_version") or 0)
        if snapshot_version > 0 and metrics.get("baseline_win_rate") is None:
            baseline = self._get_baseline_win_rate_for_snapshot(
                experiment=experiment,
                snapshot_version=snapshot_version,
            )
            if baseline is not None:
                metrics["baseline_win_rate"] = round(float(baseline), 4)
                metrics["win_rate_lift"] = round(
                    float(metrics.get("win_rate") or 0.0) - float(baseline), 4
                )

        posterior = self._update_variant_posterior(
            experiment=experiment,
            variant=selected_variant,
            metrics=metrics,
            client_id=client_id,
        )
        if posterior is not None:
            metrics["posterior"] = round(posterior, 4)

        decision_inputs, decision_outputs = self._build_and_apply_decision_policy(
            experiment=experiment,
            variant=selected_variant,
            enabled_queries=enabled_queries,
            metrics=metrics,
            client_id=client_id,
        )
        metrics["decision_action"] = decision_outputs.get("action")
        metrics["decision_policy_version"] = decision_outputs.get("policy_version")
        metrics["decision_inputs"] = decision_inputs
        metrics["decision_outputs"] = decision_outputs
        metrics["decision_refresh_of_metric_id"] = latest_metric.get("id")

        new_metric = self._deps.experiment_runs.create_metric(
            experiment_id=experiment_id,
            variant_id=selected_variant_id,
            metrics=metrics,
        )

        return {
            "experiment_id": experiment_id,
            "variant_id": selected_variant_id,
            "source_metric_id": latest_metric.get("id"),
            "new_metric_id": new_metric.get("id"),
            "posterior": metrics.get("posterior"),
            "decision_action": metrics.get("decision_action"),
            "decision_policy_version": metrics.get("decision_policy_version"),
            "status": "posterior_updated",
        }


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


def _build_retrieval_payload(
    *,
    query_text: str,
    research: Dict[str, Any] | None,
    retrieval_max_results: int,
) -> Dict[str, Any]:
    candidates = _extract_retrieval_candidates(
        research=research or {},
        limit=retrieval_max_results,
    )
    return {
        "query_text": query_text,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "insight_count": len(research.get("insights") or [])
        if isinstance(research, dict)
        else 0,
    }


def _is_control_variant(variant: Dict[str, Any]) -> bool:
    payload = variant.get("payload") or {}
    role = str(payload.get("role") or "").strip().lower()
    if role == "control":
        return True
    label = str(variant.get("label") or "").strip().lower()
    return "control" in label


def _resolve_validation_winner_variant_id(
    *,
    winner_raw: str,
    job_input_payload: Dict[str, Any],
    current_variant_id: str,
    control_variant_id: str,
) -> str | None:
    """
    Validation results may return:
    - a concrete variant_id (ideal)
    - a label (e.g. "Control (current copy)")
    - symbolic ids like "control" / "candidate" (copy_revision-style)

    This resolver normalizes those to a concrete experiment variant_id when possible.
    """
    raw = str(winner_raw or "").strip()
    if not raw:
        return None
    key = raw.strip().lower()

    # Common symbolic values.
    if key in {"control", "baseline", "control_copy"}:
        return control_variant_id or None
    if key in {"candidate", "variant", "candidate_copy"}:
        # If the job explicitly carried candidate ids, prefer those; otherwise fall back
        # to the "current" variant for which we're computing a decision signal.
        for candidate_key in ("candidate_variant_id", "variant_id", "candidate_id"):
            v = job_input_payload.get(candidate_key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        candidate_obj = job_input_payload.get("candidate")
        if isinstance(candidate_obj, dict):
            cid = candidate_obj.get("id")
            if isinstance(cid, str) and cid.strip():
                return cid.strip()
        return current_variant_id or None

    # If the raw string already matches an id in the payload variants list, accept it.
    variants = job_input_payload.get("variants")
    if isinstance(variants, list):
        for item in variants:
            if not isinstance(item, dict):
                continue
            vid = item.get("id")
            if isinstance(vid, str) and vid.strip() == raw:
                return vid.strip()
            # Map a winner "label" back to id when possible.
            label = item.get("label")
            if (
                isinstance(label, str)
                and label.strip()
                and label.strip().lower() == key
            ):
                if isinstance(vid, str) and vid.strip():
                    return vid.strip()

    # Copy-revision style payloads include explicit control/candidate objects (rare for experiments,
    # but supported here for completeness).
    control_obj = job_input_payload.get("control")
    if isinstance(control_obj, dict):
        cid = control_obj.get("id")
        if isinstance(cid, str) and cid.strip().lower() == key:
            return control_variant_id or None
    return None


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
