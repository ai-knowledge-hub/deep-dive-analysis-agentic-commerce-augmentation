from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import HTTPException

from application.ports.deps import AppDeps
from application.services.experiment.orchestrator import ExperimentOrchestrator
from application.services.experiment.runner import ExperimentRunner
from application.services.experiment.variant_generator import ExperimentVariantGenerator
from application.services.validation_service import ValidationService


@dataclass(frozen=True)
class CapabilityContext:
    client_id: str
    user_id: Optional[str]


class CapabilityExecutionError(ValueError):
    pass


def execute_capability(
    *,
    deps: AppDeps,
    context: CapabilityContext,
    capability_name: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    name = str(capability_name or "").strip()
    if name == "freeze_retrieval_protocol":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "freeze_retrieval_protocol requires experiment_id"
            )
        retrieval_max_results = int(inputs.get("retrieval_max_results") or 5)
        runner = ExperimentRunner(deps=deps)
        return runner.freeze_retrieval_protocol(
            experiment_id=experiment_id,
            client_id=context.client_id,
            user_id=context.user_id,
            retrieval_max_results=retrieval_max_results,
        )
    if name == "run_control_baseline":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "run_control_baseline requires experiment_id"
            )
        control_variant_id = _resolve_control_variant_id(
            deps=deps, experiment_id=experiment_id
        )
        if not control_variant_id:
            raise CapabilityExecutionError(
                "run_control_baseline could not find a control variant"
            )
        retrieval_max_results = int(inputs.get("retrieval_max_results") or 5)
        runner = ExperimentRunner(deps=deps)
        result = runner.run_experiment(
            experiment_id=experiment_id,
            variant_id=control_variant_id,
            client_id=context.client_id,
            user_id=context.user_id,
            execution_mode="retrieval_backed",
            retrieval_max_results=retrieval_max_results,
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": control_variant_id,
            "execution_mode": "retrieval_backed",
            "snapshot_version": (result.metrics or {}).get("snapshot_version"),
            "total_runs": (result.metrics or {}).get("total_runs"),
            "win_rate": (result.metrics or {}).get("win_rate"),
            "metric_id": (result.metrics or {}).get("metric_id"),
            "status": "baseline_scored",
        }
    if name == "seed_hypotheses":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError("seed_hypotheses requires experiment_id")
        snapshot_version_raw = inputs.get("snapshot_version")
        snapshot_version = (
            int(snapshot_version_raw) if snapshot_version_raw is not None else None
        )
        runner = ExperimentRunner(deps=deps)
        return runner.seed_hypotheses_for_snapshot(
            experiment_id=experiment_id,
            client_id=context.client_id,
            snapshot_version=snapshot_version,
        )
    if name == "generate_variants":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError("generate_variants requires experiment_id")
        mode = str(inputs.get("mode") or "loop_evidence").strip().lower()
        strategy = str(inputs.get("strategy") or "both").strip().lower()
        max_candidates = int(inputs.get("max_candidates") or 3)
        persist_count = int(inputs.get("persist_count") or max_candidates or 3)
        persist_count = max(1, min(persist_count, 5))

        generator = ExperimentVariantGenerator(deps=deps)
        generated = generator.generate_variants(
            experiment_id=experiment_id,
            client_id=context.client_id,
            max_candidates=max_candidates,
            user_id=context.user_id,
            mode=mode,
            strategy=strategy,
        )
        candidates = generated.get("candidates") or []
        created = []
        for index, item in enumerate(candidates[:persist_count], start=1):
            if not isinstance(item, dict):
                continue
            candidate_label = (
                str(item.get("label") or "").strip() or f"Candidate {index}"
            )
            candidate_description = str(item.get("description") or "").strip()
            candidate_rationale = str(item.get("rationale") or "").strip()
            candidate_confidence = item.get("confidence")
            candidate_payload = item.get("payload")
            payload_dict = (
                candidate_payload if isinstance(candidate_payload, dict) else {}
            )
            hypothesis_id = str(payload_dict.get("hypothesis_id") or "").strip() or None

            persisted_payload = {
                **payload_dict,
                "role": str(payload_dict.get("role") or "candidate"),
                "description": candidate_description,
            }
            variant = deps.experiments.add_variant(
                experiment_id=experiment_id,
                label=candidate_label,
                variant_type="hypothesis",
                payload=persisted_payload,
                hypothesis_id=hypothesis_id,
                provenance={
                    "source": "agent_runtime",
                    "capability": "generate_variants",
                    "generation_mode": generated.get("generation_mode"),
                    "generation_strategy": generated.get("generation_strategy"),
                    "candidate_index": index,
                    "candidate_rationale": candidate_rationale,
                    "candidate_confidence": candidate_confidence,
                },
            )
            created.append(
                {
                    "variant_id": variant.get("id"),
                    "label": variant.get("label"),
                    "hypothesis_id": variant.get("hypothesis_id"),
                }
            )
        return {
            "experiment_id": experiment_id,
            "generation_mode": generated.get("generation_mode"),
            "generation_strategy": generated.get("generation_strategy"),
            "requested_candidates": len(candidates),
            "persisted_count": len(created),
            "created_variants": created,
            "status": "variants_generated",
        }
    if name == "run_variant":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError("run_variant requires experiment_id")
        variant_id = str(inputs.get("variant_id") or "").strip() or None
        if not variant_id:
            variant_selection = (
                str(inputs.get("variant_selection") or "top_1").strip().lower()
            )
            variant_id = _select_candidate_variant_id(
                deps=deps,
                experiment_id=experiment_id,
                strategy=variant_selection,
            )
        if not variant_id:
            raise CapabilityExecutionError(
                "run_variant could not resolve a candidate variant"
            )
        retrieval_max_results = int(inputs.get("retrieval_max_results") or 5)
        runner = ExperimentRunner(deps=deps)
        result = runner.run_experiment(
            experiment_id=experiment_id,
            variant_id=variant_id,
            client_id=context.client_id,
            user_id=context.user_id,
            execution_mode="retrieval_backed",
            retrieval_max_results=retrieval_max_results,
        )
        metrics = result.metrics or {}
        return {
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "execution_mode": "retrieval_backed",
            "snapshot_version": metrics.get("snapshot_version"),
            "total_runs": metrics.get("total_runs"),
            "win_rate": metrics.get("win_rate"),
            "avg_score": metrics.get("avg_score"),
            "posterior": metrics.get("posterior"),
            "decision_action": metrics.get("decision_action"),
            "metric_id": metrics.get("metric_id"),
            "status": "variant_run_completed",
        }
    if name == "request_synthetic_validation":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "request_synthetic_validation requires experiment_id"
            )
        provider = str(inputs.get("provider") or "openrouter").strip().lower()
        mode = str(inputs.get("mode") or "in_app_byok").strip().lower()
        model = str(inputs.get("model") or "").strip() or None
        prompt_version = str(inputs.get("prompt_version") or "v1").strip()
        auto_run = bool(inputs.get("auto_run", True))
        target_variant_id = str(inputs.get("variant_id") or "").strip() or None
        if not target_variant_id:
            variant_selection = (
                str(inputs.get("variant_selection") or "top_1").strip().lower()
            )
            target_variant_id = _select_candidate_variant_id(
                deps=deps,
                experiment_id=experiment_id,
                strategy=variant_selection,
            )

        payload = _build_experiment_validation_payload(
            deps=deps,
            client_id=context.client_id,
            experiment_id=experiment_id,
            target_variant_id=target_variant_id,
        )
        service = ValidationService(deps=deps)
        try:
            job = service.create_job(
                client_id=context.client_id,
                brand_id=payload.get("experiment", {}).get("brand_id"),  # type: ignore[arg-type]
                product_id=payload.get("experiment", {}).get("product_id"),  # type: ignore[arg-type]
                entity_type="experiment_run",
                entity_id=experiment_id,
                provider=provider,
                mode=mode,
                model=model,
                prompt_version=prompt_version,
                input_payload=payload,
                requested_by=context.user_id,
            )
            result = None
            if auto_run and mode in {"in_app", "in_app_byok"}:
                run_result = service.run_job(job_id=str(job.get("id") or ""))
                result = run_result.get("result")
                job = run_result.get("job") or job
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            raise CapabilityExecutionError(detail) from exc

        return {
            "experiment_id": experiment_id,
            "target_variant_id": target_variant_id,
            "provider": provider,
            "mode": mode,
            "auto_run": auto_run,
            "job_id": job.get("id"),
            "job_status": job.get("status"),
            "result_id": (result or {}).get("id") if isinstance(result, dict) else None,
            "winner_id": (result or {}).get("winner_id")
            if isinstance(result, dict)
            else None,
            "score": (result or {}).get("score") if isinstance(result, dict) else None,
            "status": "synthetic_validation_requested",
        }
    if name == "review_validation_readiness":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "review_validation_readiness requires experiment_id"
            )
        variant_id = str(inputs.get("variant_id") or "").strip() or None
        if not variant_id:
            variant_selection = (
                str(inputs.get("variant_selection") or "top_1").strip().lower()
            )
            variant_id = _select_candidate_variant_id(
                deps=deps,
                experiment_id=experiment_id,
                strategy=variant_selection,
            )
        if not variant_id:
            raise CapabilityExecutionError(
                "review_validation_readiness could not resolve a candidate variant"
            )
        prod_min_coverage = _safe_float(inputs.get("prod_min_coverage"), default=0.20)
        min_verified_runs = int(inputs.get("min_verified_runs") or 3)
        min_synthetic_results = int(inputs.get("min_synthetic_results") or 1)
        readiness = _compute_validation_readiness(
            deps=deps,
            context=context,
            experiment_id=experiment_id,
            variant_id=variant_id,
            prod_min_coverage=prod_min_coverage,
            min_verified_runs=min_verified_runs,
            min_synthetic_results=min_synthetic_results,
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "readiness_state": readiness.get("readiness_state"),
            "promotion_tier": readiness.get("promotion_tier"),
            "gates": {
                "observed_ready": readiness.get("observed_ready"),
                "synthetic_ready": readiness.get("synthetic_ready"),
                "prod_min_coverage": prod_min_coverage,
                "min_verified_runs": min_verified_runs,
                "min_synthetic_results": min_synthetic_results,
            },
            "observed": readiness.get("observed"),
            "synthetic": readiness.get("synthetic"),
            "latest_decision": readiness.get("latest_decision"),
            "status": "validation_readiness_reviewed",
        }
    if name == "update_posterior_and_decisions":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "update_posterior_and_decisions requires experiment_id"
            )
        variant_id = str(inputs.get("variant_id") or "").strip() or None
        runner = ExperimentRunner(deps=deps)
        return runner.update_posterior_and_decisions(
            experiment_id=experiment_id,
            client_id=context.client_id,
            variant_id=variant_id,
        )
    if name == "recommend_next_action":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "recommend_next_action requires experiment_id"
            )
        orchestrator = ExperimentOrchestrator(deps=deps)
        recommendation = orchestrator.suggest_next_test(
            experiment_id=experiment_id,
            client_id=context.client_id,
            user_id=context.user_id,
        ).to_dict()
        deps.experiment_recommendations.create_recommendation(
            experiment_id=experiment_id,
            recommendation=recommendation,
        )
        latest_metric = (
            deps.experiment_runs.list_metrics(experiment_id=experiment_id, limit=1)
            or [{}]
        )[0]
        jobs = deps.validation_jobs.list_jobs(
            client_id=context.client_id,
            entity_type="experiment_run",
            entity_id=experiment_id,
            limit=200,
        )
        completed_jobs = [
            item
            for item in jobs
            if str(item.get("status") or "").lower() == "completed"
        ]
        return {
            "experiment_id": experiment_id,
            "recommendation": recommendation,
            "latest_metric": {
                "metric_id": latest_metric.get("id"),
                "variant_id": latest_metric.get("variant_id"),
                "decision_action": (
                    (latest_metric.get("metrics") or {}).get("decision_action")
                    if isinstance(latest_metric.get("metrics"), dict)
                    else None
                ),
                "decision_tier": (
                    (latest_metric.get("metrics") or {}).get("decision_tier")
                    if isinstance(latest_metric.get("metrics"), dict)
                    else None
                ),
                "posterior": (
                    (latest_metric.get("metrics") or {}).get("posterior")
                    if isinstance(latest_metric.get("metrics"), dict)
                    else None
                ),
            },
            "validation_summary": {
                "jobs_total": len(jobs),
                "jobs_completed": len(completed_jobs),
            },
            "status": "next_action_recommended",
        }
    if name == "promote_variant_lab":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError("promote_variant_lab requires experiment_id")
        variant_id = str(inputs.get("variant_id") or "").strip() or None
        if not variant_id:
            variant_selection = (
                str(inputs.get("variant_selection") or "top_1").strip().lower()
            )
            variant_id = _select_candidate_variant_id(
                deps=deps,
                experiment_id=experiment_id,
                strategy=variant_selection,
            )
        if not variant_id:
            raise CapabilityExecutionError(
                "promote_variant_lab could not resolve a candidate variant"
            )

        variant = deps.experiments.get_variant(variant_id)
        if not variant:
            raise CapabilityExecutionError("variant not found")
        if _is_control_variant_row(variant):
            raise CapabilityExecutionError("cannot promote control variant")

        experiment = deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=context.client_id
        )
        if not experiment:
            raise CapabilityExecutionError("experiment not found")

        latest_metric = _latest_metric_for_variant(
            deps=deps, experiment_id=experiment_id, variant_id=variant_id
        )
        if not latest_metric:
            raise CapabilityExecutionError(
                "promote_variant_lab requires a variant metric row"
            )
        metric_payload = latest_metric.get("metrics") or {}
        decision_action = (
            metric_payload.get("decision_action")
            if isinstance(metric_payload, dict)
            else None
        )
        decision_outputs = (
            metric_payload.get("decision_outputs")
            if isinstance(metric_payload, dict)
            else None
        )
        promotion_tier = (
            decision_outputs.get("promotion_tier")
            if isinstance(decision_outputs, dict)
            else None
        ) or (
            metric_payload.get("decision_tier")
            if isinstance(metric_payload, dict)
            else None
        )
        require_promote_decision = bool(inputs.get("require_promote_decision", True))
        if require_promote_decision and decision_action != "promote_variant":
            raise CapabilityExecutionError(
                "promote_variant_lab requires decision_action=promote_variant"
            )
        if str(promotion_tier or "").strip().lower() == "prod":
            raise CapabilityExecutionError(
                "decision indicates prod-tier promotion; use prod promotion path"
            )

        reason = (
            str(inputs.get("reason") or "").strip()
            or "Lab-tier promotion approved by agent runtime after policy checks."
        )
        posterior = (
            metric_payload.get("posterior")
            if isinstance(metric_payload, dict)
            else None
        )
        confidence = _safe_float(posterior, default=0.0)

        event = deps.analytics_events.create_event(
            client_id=context.client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            variant_id=variant_id,
            experiment_id=experiment_id,
            event_type="variant_promoted_lab",
            source="agent_runtime",
            event_timestamp=None,
            metadata={
                "reason": reason,
                "metric_id": latest_metric.get("id"),
                "decision_action": decision_action,
                "decision_tier": promotion_tier or "lab",
                "posterior": posterior,
                "policy_version": (
                    metric_payload.get("decision_policy_version")
                    if isinstance(metric_payload, dict)
                    else None
                ),
            },
        )
        decision_event = deps.decision_events.create_decision_event(
            client_id=context.client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            policy_action="promote_variant_lab",
            uncertainty=max(0.0, min(1.0, 1.0 - confidence)),
            expected_gain=confidence,
            selected_reason=reason,
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "promotion_tier": "lab",
            "reason": reason,
            "source_metric_id": latest_metric.get("id"),
            "posterior": posterior,
            "analytics_event_id": event.get("id"),
            "decision_event_id": decision_event.get("id"),
            "status": "variant_promoted_lab",
        }
    if name == "promote_variant_prod":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "promote_variant_prod requires experiment_id"
            )
        variant_id = str(inputs.get("variant_id") or "").strip() or None
        if not variant_id:
            variant_selection = (
                str(inputs.get("variant_selection") or "top_1").strip().lower()
            )
            variant_id = _select_candidate_variant_id(
                deps=deps,
                experiment_id=experiment_id,
                strategy=variant_selection,
            )
        if not variant_id:
            raise CapabilityExecutionError(
                "promote_variant_prod could not resolve a candidate variant"
            )

        variant = deps.experiments.get_variant(variant_id)
        if not variant:
            raise CapabilityExecutionError("variant not found")
        if _is_control_variant_row(variant):
            raise CapabilityExecutionError("cannot promote control variant")

        experiment = deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=context.client_id
        )
        if not experiment:
            raise CapabilityExecutionError("experiment not found")

        prod_min_coverage = _safe_float(inputs.get("prod_min_coverage"), default=0.20)
        min_verified_runs = int(inputs.get("min_verified_runs") or 3)
        min_synthetic_results = int(inputs.get("min_synthetic_results") or 1)
        readiness = _compute_validation_readiness(
            deps=deps,
            context=context,
            experiment_id=experiment_id,
            variant_id=variant_id,
            prod_min_coverage=prod_min_coverage,
            min_verified_runs=min_verified_runs,
            min_synthetic_results=min_synthetic_results,
        )
        if not bool(readiness.get("observed_ready")):
            raise CapabilityExecutionError(
                "promote_variant_prod requires observed readiness gate to pass"
            )

        latest_decision = readiness.get("latest_decision") or {}
        decision_action = latest_decision.get("decision_action")
        require_promote_decision = bool(inputs.get("require_promote_decision", True))
        if require_promote_decision and decision_action != "promote_variant":
            raise CapabilityExecutionError(
                "promote_variant_prod requires decision_action=promote_variant"
            )

        reason = (
            str(inputs.get("reason") or "").strip()
            or "Prod-tier promotion approved by agent runtime after observed-readiness checks."
        )
        posterior = latest_decision.get("posterior")
        confidence = _safe_float(posterior, default=0.0)
        source_metric_id = latest_decision.get("metric_id")
        decision_policy_version = latest_decision.get("decision_policy_version")

        event = deps.analytics_events.create_event(
            client_id=context.client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            variant_id=variant_id,
            experiment_id=experiment_id,
            event_type="variant_promoted_prod",
            source="agent_runtime",
            event_timestamp=None,
            metadata={
                "reason": reason,
                "metric_id": source_metric_id,
                "decision_action": decision_action,
                "decision_tier": "prod",
                "posterior": posterior,
                "policy_version": decision_policy_version,
                "readiness": {
                    "coverage_obs": (readiness.get("observed") or {}).get(
                        "coverage_obs"
                    ),
                    "verified_runs": (readiness.get("observed") or {}).get(
                        "verified_runs"
                    ),
                    "prod_min_coverage": prod_min_coverage,
                    "min_verified_runs": min_verified_runs,
                },
            },
        )
        decision_event = deps.decision_events.create_decision_event(
            client_id=context.client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            policy_action="promote_variant_prod",
            uncertainty=max(0.0, min(1.0, 1.0 - confidence)),
            expected_gain=confidence,
            selected_reason=reason,
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "promotion_tier": "prod",
            "reason": reason,
            "source_metric_id": source_metric_id,
            "posterior": posterior,
            "readiness_state": readiness.get("readiness_state"),
            "gates": {
                "observed_ready": readiness.get("observed_ready"),
                "synthetic_ready": readiness.get("synthetic_ready"),
                "prod_min_coverage": prod_min_coverage,
                "min_verified_runs": min_verified_runs,
                "min_synthetic_results": min_synthetic_results,
            },
            "analytics_event_id": event.get("id"),
            "decision_event_id": decision_event.get("id"),
            "status": "variant_promoted_prod",
        }
    if name == "publish_copy_revision":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "publish_copy_revision requires experiment_id"
            )
        variant_id = str(inputs.get("variant_id") or "").strip() or None
        if not variant_id:
            variant_selection = (
                str(inputs.get("variant_selection") or "top_1").strip().lower()
            )
            variant_id = _select_candidate_variant_id(
                deps=deps,
                experiment_id=experiment_id,
                strategy=variant_selection,
            )
        if not variant_id:
            raise CapabilityExecutionError(
                "publish_copy_revision could not resolve a candidate variant"
            )
        require_prod_promotion = bool(inputs.get("require_prod_promotion", True))

        experiment = deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=context.client_id
        )
        if not experiment:
            raise CapabilityExecutionError("experiment not found")
        variant = deps.experiments.get_variant(variant_id)
        if not variant:
            raise CapabilityExecutionError("variant not found")
        if _is_control_variant_row(variant):
            raise CapabilityExecutionError("cannot publish control variant")

        if require_prod_promotion:
            promotion_event = _latest_analytics_event_for_variant(
                deps=deps,
                client_id=context.client_id,
                experiment_id=experiment_id,
                variant_id=variant_id,
                event_type="variant_promoted_prod",
            )
            if not promotion_event:
                raise CapabilityExecutionError(
                    "publish_copy_revision requires prior prod promotion event"
                )

        product = deps.clients.get_product_for_client(
            client_id=context.client_id,
            product_id=str(experiment.get("product_id") or ""),
        )
        if not product:
            raise CapabilityExecutionError("product not found")

        revision_id = str(inputs.get("revision_id") or "").strip() or None
        revision = (
            deps.copy_revisions.get_revision(revision_id=revision_id)
            if revision_id
            else None
        )
        if revision and revision.get("client_id") != context.client_id:
            raise CapabilityExecutionError("revision scope mismatch")

        if not revision:
            revision = _find_draft_experiment_revision_for_variant(
                deps=deps,
                client_id=context.client_id,
                product_id=str(experiment.get("product_id") or ""),
                variant_id=variant_id,
            )
        if not revision:
            candidate_description = _variant_candidate_description(variant)
            if not candidate_description:
                raise CapabilityExecutionError(
                    "publish_copy_revision requires variant payload.description"
                )
            base_description = str(
                product.get("description") or product.get("name") or ""
            ).strip()
            if not base_description:
                raise CapabilityExecutionError("product has no base description")
            revision = deps.copy_revisions.create_revision(
                client_id=context.client_id,
                brand_id=experiment.get("brand_id"),
                product_id=str(experiment.get("product_id") or ""),
                source_type="experiment",
                source_id=experiment_id,
                source_variant_id=variant_id,
                base_description=base_description,
                candidate_description=candidate_description,
                notes="Auto-created by agent runtime publish_copy_revision.",
                metadata={
                    "source": "agent_runtime",
                    "capability": "publish_copy_revision",
                    "variant_label": variant.get("label"),
                },
                created_by=context.user_id,
            )

        metadata = dict(product.get("metadata") or {})
        copy_meta = dict(metadata.get("copy_revision") or {})
        copy_meta.update(
            {
                "latest_revision_id": revision.get("id"),
                "latest_revision_source": revision.get("source_type"),
                "published_at": revision.get("updated_at"),
                "published_by": "agent_runtime",
            }
        )
        metadata["copy_revision"] = copy_meta
        updated_product = deps.clients.update_product(
            product_id=str(experiment.get("product_id") or ""),
            description=str(revision.get("candidate_description") or ""),
            metadata=metadata,
        )
        updated_revision = deps.copy_revisions.update_revision_status(
            revision_id=str(revision.get("id") or ""),
            status="published",
            approved_by=context.user_id,
            notes=str(inputs.get("notes") or "").strip() or None,
        )
        event = deps.analytics_events.create_event(
            client_id=context.client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            variant_id=variant_id,
            experiment_id=experiment_id,
            event_type="copy_revision_published",
            source="agent_runtime",
            event_timestamp=None,
            metadata={
                "revision_id": (updated_revision or {}).get("id"),
                "variant_id": variant_id,
                "product_id": experiment.get("product_id"),
                "require_prod_promotion": require_prod_promotion,
            },
        )
        decision_event = deps.decision_events.create_decision_event(
            client_id=context.client_id,
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            policy_action="publish_copy_revision",
            selected_reason="Copy revision published from prod-promoted variant.",
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "revision_id": (updated_revision or {}).get("id"),
            "product_id": experiment.get("product_id"),
            "product_description_updated": bool(updated_product),
            "analytics_event_id": event.get("id"),
            "decision_event_id": decision_event.get("id"),
            "status": "copy_revision_published",
        }

    raise CapabilityExecutionError(f"Unsupported capability: {name}")


def _resolve_control_variant_id(*, deps: AppDeps, experiment_id: str) -> str | None:
    variants = deps.experiments.list_variants(experiment_id=experiment_id)
    for variant in variants:
        payload = variant.get("payload") or {}
        role = str(payload.get("role") or "").strip().lower()
        if role == "control":
            return str(variant.get("id") or "")
    for variant in variants:
        label = str(variant.get("label") or "").strip().lower()
        if "control" in label:
            return str(variant.get("id") or "")
    return None


def _select_candidate_variant_id(
    *, deps: AppDeps, experiment_id: str, strategy: str
) -> str | None:
    variants = deps.experiments.list_variants(experiment_id=experiment_id)
    candidates = [
        v for v in variants if str(v.get("id") or "") and not _is_control_variant_row(v)
    ]
    if not candidates:
        return None
    # Current v0 strategies map to newest-first non-control selection.
    # We can later add Thompson/policy-aware selection here.
    if strategy in {"top_1", "latest", "newest"}:
        return str(candidates[0].get("id") or "")
    return str(candidates[0].get("id") or "")


def _is_control_variant_row(variant: Dict[str, Any]) -> bool:
    payload = variant.get("payload") or {}
    role = str(payload.get("role") or "").strip().lower()
    if role == "control":
        return True
    label = str(variant.get("label") or "").strip().lower()
    return "control" in label


def _build_experiment_validation_payload(
    *,
    deps: AppDeps,
    client_id: str,
    experiment_id: str,
    target_variant_id: Optional[str],
) -> Dict[str, Any]:
    experiment = deps.experiments.get_experiment(
        experiment_id=experiment_id, client_id=client_id
    )
    if not experiment:
        raise CapabilityExecutionError("experiment not found for validation payload")
    runs = deps.experiment_runs.list_runs(experiment_id=experiment_id, limit=500)
    metrics = deps.experiment_runs.list_metrics(experiment_id=experiment_id, limit=500)
    variants = deps.experiments.list_variants(experiment_id=experiment_id)
    return {
        "type": "experiment",
        "experiment": experiment,
        "runs": runs,
        "metrics": metrics,
        "variants": variants,
        "target_variant_id": target_variant_id,
    }


def _latest_metric_for_variant(
    *, deps: AppDeps, experiment_id: str, variant_id: str
) -> Dict[str, Any] | None:
    rows = deps.experiment_runs.list_metrics(experiment_id=experiment_id, limit=500)
    for row in rows:
        if str(row.get("variant_id") or "") == str(variant_id):
            return row
    return None


def _extract_observed_coverage(
    *,
    deps: AppDeps,
    experiment: Dict[str, Any],
    experiment_id: str,
    variant_id: str,
    decision_inputs: Dict[str, Any] | None,
) -> float:
    if decision_inputs:
        try:
            return max(0.0, min(1.0, float(decision_inputs.get("coverage_obs") or 0.0)))
        except (TypeError, ValueError):
            pass

    battery_id = str(experiment.get("battery_id") or "").strip()
    queries = deps.batteries.list_queries(battery_id=battery_id) if battery_id else []
    enabled_queries = [
        item
        for item in queries
        if bool(item.get("enabled", True)) and str(item.get("query_text") or "").strip()
    ]
    validations = deps.experiment_validations.list_validations(
        experiment_id=experiment_id, limit=500
    )
    distinct_q = {
        str(v.get("query_text") or "").strip().lower()
        for v in validations
        if str(v.get("variant_id") or "") == str(variant_id)
        and str(v.get("query_text") or "").strip()
    }
    if not enabled_queries:
        return 0.0
    return max(0.0, min(1.0, len(distinct_q) / len(enabled_queries)))


def _compute_validation_readiness(
    *,
    deps: AppDeps,
    context: CapabilityContext,
    experiment_id: str,
    variant_id: str,
    prod_min_coverage: float,
    min_verified_runs: int,
    min_synthetic_results: int,
) -> Dict[str, Any]:
    experiment = deps.experiments.get_experiment(
        experiment_id=experiment_id, client_id=context.client_id
    )
    if not experiment:
        raise CapabilityExecutionError("experiment not found")

    latest_metric = _latest_metric_for_variant(
        deps=deps,
        experiment_id=experiment_id,
        variant_id=variant_id,
    )
    metric_payload = (latest_metric or {}).get("metrics") or {}
    decision_inputs = (
        metric_payload.get("decision_inputs")
        if isinstance(metric_payload, dict)
        else None
    )
    coverage_obs = _extract_observed_coverage(
        deps=deps,
        experiment=experiment,
        experiment_id=experiment_id,
        variant_id=variant_id,
        decision_inputs=decision_inputs if isinstance(decision_inputs, dict) else None,
    )
    observed_summary = deps.experiment_validations.accuracy_summary(
        experiment_id=experiment_id,
        client_id=context.client_id,
    )
    verified_runs = int(observed_summary.get("verified_runs") or 0)
    jobs = deps.validation_jobs.list_jobs(
        client_id=context.client_id,
        entity_type="experiment_run",
        entity_id=experiment_id,
        limit=200,
    )
    completed_jobs = [
        item for item in jobs if str(item.get("status") or "").lower() == "completed"
    ]
    scored_results = 0
    for job in completed_jobs:
        result = deps.validation_results.get_latest_for_job(
            job_id=str(job.get("id") or "")
        )
        if not result:
            continue
        if result.get("score") is not None or result.get("winner_id"):
            scored_results += 1

    observed_ready = (coverage_obs >= prod_min_coverage) and (
        verified_runs >= min_verified_runs
    )
    synthetic_ready = scored_results >= min_synthetic_results
    promotion_tier = "prod" if observed_ready else "lab"
    readiness_state = (
        "ready_for_prod"
        if observed_ready
        else "ready_for_lab"
        if synthetic_ready
        else "needs_more_validation"
    )
    return {
        "readiness_state": readiness_state,
        "promotion_tier": promotion_tier,
        "observed_ready": observed_ready,
        "synthetic_ready": synthetic_ready,
        "observed": {
            "coverage_obs": round(coverage_obs, 6),
            "verified_runs": verified_runs,
            "correct_runs": int(observed_summary.get("correct_runs") or 0),
            "accuracy": observed_summary.get("accuracy"),
        },
        "synthetic": {
            "jobs_total": len(jobs),
            "jobs_completed": len(completed_jobs),
            "results_scored": scored_results,
        },
        "latest_decision": {
            "decision_action": metric_payload.get("decision_action")
            if isinstance(metric_payload, dict)
            else None,
            "decision_tier": metric_payload.get("decision_tier")
            if isinstance(metric_payload, dict)
            else None,
            "posterior": metric_payload.get("posterior")
            if isinstance(metric_payload, dict)
            else None,
            "decision_policy_version": metric_payload.get("decision_policy_version")
            if isinstance(metric_payload, dict)
            else None,
            "metric_id": (latest_metric or {}).get("id"),
        },
    }


def _latest_analytics_event_for_variant(
    *,
    deps: AppDeps,
    client_id: str,
    experiment_id: str,
    variant_id: str,
    event_type: str,
) -> Dict[str, Any] | None:
    events = deps.analytics_events.list_events(
        client_id=client_id,
        experiment_id=experiment_id,
        limit=500,
    )
    for event in events:
        if str(event.get("event_type") or "") != str(event_type):
            continue
        if str(event.get("variant_id") or "") != str(variant_id):
            continue
        return event
    return None


def _find_draft_experiment_revision_for_variant(
    *,
    deps: AppDeps,
    client_id: str,
    product_id: str,
    variant_id: str,
) -> Dict[str, Any] | None:
    revisions = deps.copy_revisions.list_revisions(
        client_id=client_id,
        product_id=product_id,
        source_type="experiment",
        limit=200,
    )
    for revision in revisions:
        if str(revision.get("source_variant_id") or "") != str(variant_id):
            continue
        if str(revision.get("status") or "").strip().lower() != "draft":
            continue
        return revision
    return None


def _variant_candidate_description(variant: Dict[str, Any]) -> str:
    payload = variant.get("payload") or {}
    if isinstance(payload, dict):
        return str(payload.get("description") or "").strip()
    return ""


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


__all__ = [
    "CapabilityContext",
    "CapabilityExecutionError",
    "execute_capability",
]
