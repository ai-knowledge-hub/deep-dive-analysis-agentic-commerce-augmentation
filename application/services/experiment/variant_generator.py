from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from application.ports.deps import AppDeps


@dataclass(frozen=True)
class GeneratedVariantCandidate:
    label: str
    description: str
    rationale: str
    payload: Dict[str, Any]
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "description": self.description,
            "rationale": self.rationale,
            "payload": self.payload,
            "confidence": round(self.confidence, 3),
        }


class ExperimentVariantGenerator:
    """Generates variant candidates from loop evidence or cold-start context."""

    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def generate_from_loop_evidence(
        self,
        *,
        experiment_id: str,
        client_id: str,
        max_candidates: int = 3,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.generate_variants(
            experiment_id=experiment_id,
            client_id=client_id,
            max_candidates=max_candidates,
            user_id=user_id,
            mode="loop_evidence",
            strategy="both",
        )

    def generate_variants(
        self,
        *,
        experiment_id: str,
        client_id: str,
        max_candidates: int = 3,
        user_id: Optional[str] = None,
        mode: str = "loop_evidence",
        strategy: str = "both",
    ) -> Dict[str, Any]:
        normalized_mode = (mode or "loop_evidence").strip().lower()
        normalized_strategy = _normalize_strategy(strategy)
        if normalized_mode not in {"loop_evidence", "cold_start"}:
            raise ValueError("invalid generation mode")

        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")

        product = self._deps.clients.get_product_for_client(
            client_id=client_id, product_id=experiment["product_id"]
        )
        if not product:
            raise ValueError("product not found for experiment")

        bounded_max_candidates = max(1, min(max_candidates, 5))
        evidence: Dict[str, Any]
        summary: Dict[str, Any]
        candidates: List[GeneratedVariantCandidate]
        used_fallback = False

        if normalized_mode == "cold_start":
            evidence, summary = _build_cold_start_packet(
                experiment=experiment,
                product=product,
                strategy=normalized_strategy,
                max_candidates=bounded_max_candidates,
            )
            prompt = _build_cold_start_prompt(
                experiment=experiment,
                product=product,
                evidence=evidence,
                strategy=normalized_strategy,
                max_candidates=bounded_max_candidates,
            )
            raw = self._deps.generate(prompt)
            parsed = _parse_candidates(
                raw,
                default_source_type="cold_start",
                default_generation_strategy=normalized_strategy,
            )
            candidates = parsed
            if not candidates:
                candidates = _fallback_cold_start_candidates(
                    summary=summary,
                    product=product,
                    strategy=normalized_strategy,
                    max_candidates=bounded_max_candidates,
                )
                used_fallback = True
        else:
            variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
            metrics = self._deps.experiment_runs.list_metrics(
                experiment_id=experiment_id, limit=200
            )
            runs = self._deps.experiment_runs.list_runs(
                experiment_id=experiment_id, limit=500
            )
            validations = self._deps.experiment_validations.list_validations(
                experiment_id=experiment_id, client_id=client_id, limit=100
            )
            revisions = self._deps.copy_revisions.list_revisions(
                client_id=client_id,
                product_id=experiment["product_id"],
                limit=100,
            )

            evidence, summary = _build_evidence_packet(
                deps=self._deps,
                experiment=experiment,
                product=product,
                variants=variants,
                metrics=metrics,
                runs=runs,
                validations=validations,
                revisions=revisions,
            )

            prompt = _build_prompt(
                experiment=experiment,
                product=product,
                evidence=evidence,
                max_candidates=bounded_max_candidates,
            )
            raw = self._deps.generate(prompt)
            parsed = _parse_candidates(raw, default_source_type="loop_evidence")
            candidates = parsed

            if not candidates:
                candidates = _fallback_candidates(summary=summary, product=product)
                used_fallback = True

        return {
            "experiment_id": experiment_id,
            "product_id": experiment.get("product_id"),
            "generation_mode": normalized_mode,
            "generation_strategy": normalized_strategy,
            "summary": summary,
            "evidence": evidence,
            "candidates": [
                item.to_dict() for item in candidates[:bounded_max_candidates]
            ],
            "used_fallback": used_fallback,
            "requested_by": user_id,
        }


def _build_evidence_packet(
    *,
    deps: AppDeps,
    experiment: Dict[str, Any],
    product: Dict[str, Any],
    variants: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    validations: List[Dict[str, Any]],
    revisions: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    latest_metric_by_variant: Dict[str, Dict[str, Any]] = {}
    for metric in metrics:
        variant_id = metric.get("variant_id")
        if not variant_id:
            continue
        existing = latest_metric_by_variant.get(variant_id)
        if not existing or (metric.get("created_at") or "") > (
            existing.get("created_at") or ""
        ):
            latest_metric_by_variant[variant_id] = metric

    control_variant = _find_control_variant(variants)
    best_variant = _find_best_variant(variants, latest_metric_by_variant)

    control_metrics = (
        latest_metric_by_variant.get(control_variant.get("id") or "", {}).get("metrics")
        if control_variant
        else None
    ) or {}
    best_metrics = (
        latest_metric_by_variant.get(best_variant.get("id") or "", {}).get("metrics")
        if best_variant
        else None
    ) or {}

    control_win_rate = _safe_float(control_metrics.get("win_rate"))
    best_win_rate = _safe_float(best_metrics.get("win_rate"))
    performance_gap = None
    if control_win_rate is not None and best_win_rate is not None:
        performance_gap = round(best_win_rate - control_win_rate, 4)

    missing_signal_counts: Dict[str, int] = {}
    winner_signal_counts: Dict[str, int] = {}
    linked_simulation_count = 0
    for run in runs:
        sim_run_id = run.get("simulation_run_id")
        if not sim_run_id:
            continue
        sim_run = deps.simulation_runs.get_run(sim_run_id)
        if not sim_run:
            continue
        gap_analysis = (sim_run.get("result") or {}).get("gap_analysis") or []
        if not isinstance(gap_analysis, list) or not gap_analysis:
            continue
        linked_simulation_count += 1
        target_gap = next(
            (
                item
                for item in gap_analysis
                if item.get("product_id") == experiment.get("product_id")
            ),
            gap_analysis[0],
        )
        for signal in target_gap.get("missing_signals") or []:
            if not signal:
                continue
            key = str(signal).strip()
            if not key:
                continue
            missing_signal_counts[key] = missing_signal_counts.get(key, 0) + 1
        for signal in target_gap.get("winner_signals") or []:
            if not signal:
                continue
            key = str(signal).strip()
            if not key:
                continue
            winner_signal_counts[key] = winner_signal_counts.get(key, 0) + 1

    validation_correct = sum(1 for row in validations if row.get("is_correct") is True)
    validation_verified = sum(
        1 for row in validations if row.get("is_correct") in {True, False}
    )
    validation_accuracy = (
        round(validation_correct / validation_verified, 4)
        if validation_verified
        else None
    )

    revision_groups = {
        "simulation": [
            row for row in revisions if row.get("source_type") == "simulation"
        ],
        "experiment": [
            row for row in revisions if row.get("source_type") == "experiment"
        ],
        "other": [
            row
            for row in revisions
            if row.get("source_type") not in {"simulation", "experiment"}
        ],
    }

    evidence = {
        "reliability_weights": {
            "validation_observed": 1.0,
            "experiment_simulated": 0.7,
            "simulation_revisions": 0.45,
        },
        "control_context": {
            "product_name": product.get("name"),
            "control_variant_id": control_variant.get("id")
            if control_variant
            else None,
            "control_variant_label": control_variant.get("label")
            if control_variant
            else None,
            "control_win_rate": control_win_rate,
            "best_variant_id": best_variant.get("id") if best_variant else None,
            "best_variant_label": best_variant.get("label") if best_variant else None,
            "best_win_rate": best_win_rate,
            "performance_gap": performance_gap,
        },
        "experiment_evidence": {
            "variant_count": len(variants),
            "metrics_count": len(metrics),
            "runs_count": len(runs),
            "latest_metrics_by_variant": [
                {
                    "variant_id": variant.get("id"),
                    "label": variant.get("label"),
                    "type": variant.get("type"),
                    "metrics": (
                        latest_metric_by_variant.get(variant.get("id", "")) or {}
                    ).get("metrics", {}),
                }
                for variant in variants
            ],
            "top_missing_signals": _top_items(missing_signal_counts),
            "top_winner_signals": _top_items(winner_signal_counts),
            "linked_simulation_runs": linked_simulation_count,
        },
        "simulation_revision_evidence": {
            "count": len(revision_groups["simulation"]),
            "latest": [
                {
                    "id": row.get("id"),
                    "status": row.get("status"),
                    "candidate_description": row.get("candidate_description"),
                    "notes": row.get("notes"),
                    "updated_at": row.get("updated_at"),
                }
                for row in revision_groups["simulation"][:5]
            ],
        },
        "experiment_revision_evidence": {
            "count": len(revision_groups["experiment"]),
            "latest": [
                {
                    "id": row.get("id"),
                    "status": row.get("status"),
                    "candidate_description": row.get("candidate_description"),
                    "notes": row.get("notes"),
                    "updated_at": row.get("updated_at"),
                }
                for row in revision_groups["experiment"][:5]
            ],
        },
        "validation_evidence": {
            "total": len(validations),
            "verified": validation_verified,
            "correct": validation_correct,
            "accuracy": validation_accuracy,
            "recent": [
                {
                    "id": row.get("id"),
                    "variant_id": row.get("variant_id"),
                    "query_text": row.get("query_text"),
                    "observed_winner_variant_id": row.get("observed_winner_variant_id"),
                    "is_correct": row.get("is_correct"),
                    "notes": row.get("notes"),
                    "created_at": row.get("created_at"),
                }
                for row in validations[:8]
            ],
        },
    }

    summary = {
        "control_variant_label": control_variant.get("label")
        if control_variant
        else None,
        "best_variant_label": best_variant.get("label") if best_variant else None,
        "control_win_rate": control_win_rate,
        "best_win_rate": best_win_rate,
        "performance_gap": performance_gap,
        "top_missing_signals": [
            item["signal"] for item in _top_items(missing_signal_counts)
        ],
        "top_winner_signals": [
            item["signal"] for item in _top_items(winner_signal_counts)
        ],
        "validation_accuracy": validation_accuracy,
        "simulation_revision_count": len(revision_groups["simulation"]),
        "experiment_revision_count": len(revision_groups["experiment"]),
    }
    return evidence, summary


def _find_control_variant(variants: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for variant in variants:
        payload = variant.get("payload") or {}
        role = str(payload.get("role") or "").lower()
        if role == "control":
            return variant
    for variant in variants:
        label = str(variant.get("label") or "").lower()
        if "control" in label:
            return variant
    return variants[0] if variants else None


def _find_best_variant(
    variants: List[Dict[str, Any]], latest_metric_by_variant: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    best_rate: Optional[float] = None
    for variant in variants:
        metric = latest_metric_by_variant.get(variant.get("id") or "")
        rate = _safe_float((metric or {}).get("metrics", {}).get("win_rate"))
        if rate is None:
            continue
        if best is None or best_rate is None or rate > best_rate:
            best = variant
            best_rate = rate
    return best or (variants[0] if variants else None)


def _top_items(counts: Dict[str, int], limit: int = 6) -> List[Dict[str, Any]]:
    return [
        {"signal": key, "count": value}
        for key, value in sorted(
            counts.items(), key=lambda item: item[1], reverse=True
        )[:limit]
    ]


def _build_prompt(
    *,
    experiment: Dict[str, Any],
    product: Dict[str, Any],
    evidence: Dict[str, Any],
    max_candidates: int,
) -> str:
    payload = {
        "task": "generate_copy_variants_from_closed_loop_evidence",
        "experiment": {
            "id": experiment.get("id"),
            "name": experiment.get("name"),
            "hypothesis": experiment.get("hypothesis"),
            "competitor_policy": experiment.get("competitor_policy"),
        },
        "product": {
            "id": product.get("id"),
            "name": product.get("name"),
            "description": product.get("description"),
        },
        "evidence": evidence,
        "rules": {
            "max_candidates": max_candidates,
            "prefer_observed_validation_signals": True,
            "require_factual_grounding": True,
            "must_include_actionable_rationale": True,
            "return_format": "json",
        },
    }
    return (
        "You are a senior experimentation strategist for commerce copy optimization.\n"
        "Goal: generate candidate copy variants that close the control performance gap.\n"
        "Use reliability hierarchy exactly: validation_observed > experiment_simulated > simulation_revisions.\n"
        "Never invent product facts. Keep copy concise and outcome-led.\n"
        "Return ONLY JSON with shape:\n"
        '{"candidates":[{"label":"string","description":"string","rationale":"string","confidence":0.0,'
        '"payload":{"role":"candidate","source_type":"loop_evidence","evidence_basis":["validation|experiment|simulation"],'
        '"control_gap":{"metric":"win_rate","delta":0.0}}}]}\n'
        "No markdown, no commentary.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _build_cold_start_packet(
    *,
    experiment: Dict[str, Any],
    product: Dict[str, Any],
    strategy: str,
    max_candidates: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    metadata = product.get("metadata") or {}
    features = _collect_context_list(
        [
            metadata.get("features"),
            (metadata.get("canonical_intent_spec") or {}).get("feature_concepts"),
            metadata.get("capabilities"),
            metadata.get("benefits"),
        ]
    )
    use_cases = _collect_context_list(
        [
            metadata.get("use_case"),
            metadata.get("scenario"),
            (metadata.get("canonical_intent_spec") or {}).get("use_cases"),
        ]
    )
    audience_segments = _collect_context_list(
        [
            metadata.get("audience_segments"),
            metadata.get("audience_archetypes"),
            metadata.get("target_audience"),
            (metadata.get("canonical_intent_spec") or {}).get("audience_archetypes"),
        ]
    )
    user_goals = _collect_context_list(
        [
            metadata.get("goals_served"),
            metadata.get("outcomes_expected"),
            metadata.get("jobs_to_be_done"),
            (metadata.get("canonical_intent_spec") or {}).get("goals_served"),
        ]
    )
    inferred_intents = _merge_unique_text_lists(
        [use_cases[:4], user_goals[:4], features[:2]]
    )[:6]
    if not inferred_intents:
        inferred_intents = ["faster decision-making", "better outcome confidence"]

    evidence = {
        "generation_context": {
            "mode": "cold_start",
            "strategy": strategy,
            "max_candidates": max_candidates,
            "allow_brand_mentions": True,
            "allow_metadata_mentions": True,
            "alignment_priority": "user_intent_needs_goals",
        },
        "experiment_context": {
            "id": experiment.get("id"),
            "name": experiment.get("name"),
            "hypothesis": experiment.get("hypothesis"),
            "competitor_policy": experiment.get("competitor_policy"),
        },
        "product_context": {
            "id": product.get("id"),
            "name": product.get("name"),
            "description": product.get("description"),
            "brand_signals": _collect_context_list(
                [
                    metadata.get("brand"),
                    metadata.get("merchant_name"),
                    metadata.get("manufacturer"),
                    metadata.get("brand_voice"),
                    metadata.get("positioning"),
                ]
            )[:6],
            "features": features[:10],
            "use_cases": use_cases[:10],
            "audience_segments": audience_segments[:8],
            "user_goals": user_goals[:8],
            "inferred_intents": inferred_intents,
        },
    }
    summary = {
        "context_source": "cold_start",
        "strategy": strategy,
        "feature_count": len(features),
        "use_case_count": len(use_cases),
        "audience_segment_count": len(audience_segments),
        "goal_count": len(user_goals),
        "inferred_intents": inferred_intents,
    }
    return evidence, summary


def _build_cold_start_prompt(
    *,
    experiment: Dict[str, Any],
    product: Dict[str, Any],
    evidence: Dict[str, Any],
    strategy: str,
    max_candidates: int,
) -> str:
    strategy_rule = {
        "bottom_up": "Start from concrete features/use-cases and map each claim to user needs.",
        "top_down": "Start from user outcomes and positioning narrative, then anchor to available facts.",
        "both": "Blend outcome-led narrative with concrete feature/use-case grounding.",
    }.get(strategy, "Blend outcome-led narrative with concrete grounding.")

    payload = {
        "task": "generate_copy_variants_from_cold_start_product_context",
        "experiment": {
            "id": experiment.get("id"),
            "name": experiment.get("name"),
            "hypothesis": experiment.get("hypothesis"),
        },
        "product": {
            "id": product.get("id"),
            "name": product.get("name"),
            "description": product.get("description"),
        },
        "evidence": evidence,
        "rules": {
            "max_candidates": max_candidates,
            "generation_strategy": strategy,
            "allow_brand_mentions": True,
            "allow_metadata_mentions": True,
            "require_intent_alignment": True,
            "require_factual_grounding": True,
            "must_include_actionable_rationale": True,
            "return_format": "json",
        },
    }
    return (
        "You are a senior commerce copy strategist generating cold-start variant candidates.\n"
        "Goal: propose copy variants aligned to inferred user intent, needs, and goals.\n"
        "Brand and metadata mentions are allowed when grounded in provided product context.\n"
        f"Strategy: {strategy_rule}\n"
        "Never invent product facts. Keep copy concise, specific, and user-outcome oriented.\n"
        "Return ONLY JSON with shape:\n"
        '{"candidates":[{"label":"string","description":"string","rationale":"string","confidence":0.0,'
        '"payload":{"role":"candidate","source_type":"cold_start","generation_strategy":"bottom_up|top_down|both",'
        '"intent_focus":["string"],"alignment_basis":["product_features|audience_segment|user_goal"]}}]}\n'
        "No markdown, no commentary.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_candidates(
    raw: str,
    *,
    default_source_type: str,
    default_generation_strategy: Optional[str] = None,
) -> List[GeneratedVariantCandidate]:
    if not raw:
        return []
    trimmed = raw.strip()
    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            parsed = json.loads(trimmed[start : end + 1])
        except json.JSONDecodeError:
            return []
    items = parsed.get("candidates")
    if not isinstance(items, list):
        return []
    cleaned: List[GeneratedVariantCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not description or not rationale:
            continue
        label = str(item.get("label") or "Loop candidate").strip() or "Loop candidate"
        payload = item.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        payload = {
            **payload,
            "role": str(payload.get("role") or "candidate"),
            "source_type": str(payload.get("source_type") or default_source_type),
        }
        if default_generation_strategy and not payload.get("generation_strategy"):
            payload["generation_strategy"] = default_generation_strategy
        confidence = _safe_float(item.get("confidence")) or 0.55
        cleaned.append(
            GeneratedVariantCandidate(
                label=label,
                description=description,
                rationale=rationale,
                payload=payload,
                confidence=max(0.0, min(confidence, 1.0)),
            )
        )
    return cleaned


def _fallback_candidates(
    *, summary: Dict[str, Any], product: Dict[str, Any]
) -> List[GeneratedVariantCandidate]:
    missing = summary.get("top_missing_signals") or []
    winner = summary.get("top_winner_signals") or []
    product_name = str(product.get("name") or "the product")
    missing_text = ", ".join(missing[:2]) if missing else "key user priorities"
    winner_text = ", ".join(winner[:2]) if winner else "winning outcome signals"
    description = (
        f"{product_name} helps users achieve {winner_text} while directly addressing {missing_text}. "
        "Copy emphasizes concrete outcomes and clear decision criteria."
    )
    payload = {
        "role": "candidate",
        "source_type": "loop_evidence",
        "evidence_basis": ["experiment", "simulation"],
        "control_gap": {"metric": "win_rate", "delta": summary.get("performance_gap")},
    }
    return [
        GeneratedVariantCandidate(
            label="Loop-informed candidate",
            description=description,
            rationale=(
                "Fallback candidate generated from observed missing and winner signals "
                "because model output was unavailable or invalid."
            ),
            payload=payload,
            confidence=0.5,
        )
    ]


def _fallback_cold_start_candidates(
    *,
    summary: Dict[str, Any],
    product: Dict[str, Any],
    strategy: str,
    max_candidates: int,
) -> List[GeneratedVariantCandidate]:
    product_name = str(product.get("name") or "the product")
    intents = summary.get("inferred_intents") or []
    primary_intent = str(intents[0] if intents else "core user goals")
    secondary_intent = str(
        intents[1]
        if isinstance(intents, list) and len(intents) > 1
        else "decision clarity"
    )
    templates = [
        (
            "Intent-aligned outcome variant",
            (
                f"{product_name} is built to support {primary_intent} with clear value, "
                "simple decision framing, and confidence in the end result."
            ),
            "Uses inferred user intent and goals from product context for cold-start copy generation.",
            0.56,
        ),
        (
            "Audience-fit value variant",
            (
                f"{product_name} balances practical benefits and trusted context for users seeking "
                f"{secondary_intent}."
            ),
            "Balances product context with inferred audience expectations in absence of experiment history.",
            0.53,
        ),
    ]
    if strategy == "bottom_up":
        templates[0] = (
            "Feature-led cold-start variant",
            (
                f"{product_name} highlights concrete capabilities and practical use-cases that support "
                f"{primary_intent}."
            ),
            "Bottom-up fallback grounded in product features and use-cases.",
            0.56,
        )
    elif strategy == "top_down":
        templates[0] = (
            "Narrative-led cold-start variant",
            (
                f"{product_name} leads with user outcomes and positioning for people prioritizing "
                f"{primary_intent}."
            ),
            "Top-down fallback grounded in user outcomes and audience context.",
            0.56,
        )

    candidates: List[GeneratedVariantCandidate] = []
    for label, description, rationale, confidence in templates[
        : max(1, max_candidates)
    ]:
        candidates.append(
            GeneratedVariantCandidate(
                label=label,
                description=description,
                rationale=rationale,
                payload={
                    "role": "candidate",
                    "source_type": "cold_start",
                    "generation_strategy": strategy,
                    "alignment_basis": ["product_context", "audience_context"],
                    "intent_focus": intents[:3] if isinstance(intents, list) else [],
                },
                confidence=confidence,
            )
        )
    return candidates


def _normalize_strategy(value: str) -> str:
    normalized = (value or "both").strip().lower()
    if normalized in {"both", "hybrid"}:
        return "both"
    if normalized in {"bottom_up", "top_down"}:
        return normalized
    raise ValueError("invalid generation strategy")


def _collect_context_list(values: List[Any]) -> List[str]:
    output: List[str] = []
    for value in values:
        if isinstance(value, str):
            parts = re.split(r"[,\n;|]+", value)
            output.extend(part.strip() for part in parts if part and part.strip())
            continue
        if isinstance(value, list):
            output.extend(str(item).strip() for item in value if str(item).strip())
            continue
        if isinstance(value, dict):
            output.extend(
                str(item).strip()
                for item in value.values()
                if isinstance(item, (str, int, float)) and str(item).strip()
            )
    return _merge_unique_text_lists([output])


def _merge_unique_text_lists(items: List[List[str]]) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()
    for group in items:
        for item in group:
            cleaned = str(item).strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(cleaned)
    return merged


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["ExperimentVariantGenerator", "GeneratedVariantCandidate"]
