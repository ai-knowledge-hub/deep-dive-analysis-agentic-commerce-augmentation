from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from application.services.replay import default_versions
from llm.agents.harness.replay_logger import ReplayRecord, ToolCall
from modules.memory.repositories import replays as replays_repo
from modules.alignment import goal_alignment
from modules.evidence import (
    EvidenceProduct,
    retrieve as default_retrieve,
    to_product,
    optimize,
)
from modules.evidence.verify import average_alignment, simulate_actual
from modules.intent.llm_classifier import HybridIntentClassifier
from modules.intentionality.profiling import build_profile


class EvidenceService:
    def analyze(
        self,
        *,
        query: str,
        max_items: int = 5,
        retrieve_fn=default_retrieve,
        client_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        classifier = HybridIntentClassifier()
        intent = classifier.classify(query).to_dict()
        goals = _intent_goals(intent, fallback=query)

        start = time.perf_counter()
        evidence_products = retrieve_fn(query, max_items=max_items)
        retrieve_ms = int((time.perf_counter() - start) * 1000)
        products = [to_product(item) for item in evidence_products]
        profiles = [build_profile(product).to_dict() for product in products]
        score_start = time.perf_counter()
        alignment_scores = goal_alignment.score_products(goals, products)
        score_ms = int((time.perf_counter() - score_start) * 1000)

        replay = ReplayRecord(
            run_type="evidence.analyze",
            inputs={"query": query, "max_items": max_items},
            outputs={"count": len(evidence_products)},
            tool_calls=[
                ToolCall(
                    name="retrieve_evidence",
                    arguments={"query": query, "max_items": max_items},
                    result_summary=f"items={len(evidence_products)}",
                    elapsed_ms=retrieve_ms,
                ),
                ToolCall(
                    name="score_products",
                    arguments={
                        "goal_count": len(goals),
                        "product_count": len(products),
                    },
                    result_summary="alignment_scores",
                    elapsed_ms=score_ms,
                ),
            ],
            versions=default_versions(),
        )
        replay_id = None
        if client_id:
            replay_id = replays_repo.create_replay_record(
                run_type="evidence.analyze",
                record=replay.to_dict(),
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
                entity_type="evidence_flow",
                entity_id=query,
            ).get("id")

        return {
            "intent": intent,
            "goals": goals,
            "evidence_products": [
                _evidence_to_dict(item) for item in evidence_products
            ],
            "profiles": profiles,
            "alignment_scores": [score.__dict__ for score in alignment_scores],
            "replay": replay.to_dict(),
            "replay_id": replay_id,
        }

    def optimize_representation(
        self,
        *,
        evidence_products: List[EvidenceProduct],
        query: Optional[str] = None,
        tone: Optional[str] = None,
        client_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        intent = None
        goals: List[str] = []
        if query:
            classifier = HybridIntentClassifier()
            intent = classifier.classify(query).to_dict()
            goals = _intent_goals(intent, fallback=query)

        start = time.perf_counter()
        optimized_pairs = optimize(evidence_products, goals=goals or None, tone=tone)
        optimize_ms = int((time.perf_counter() - start) * 1000)

        before_products = [to_product(item) for item in evidence_products]
        after_products = [
            _product_with_description(product, pair["after"])
            for product, pair in zip(before_products, optimized_pairs)
        ]
        score_start = time.perf_counter()
        before_scores = goal_alignment.score_products(goals, before_products)
        after_scores = goal_alignment.score_products(goals, after_products)
        score_ms = int((time.perf_counter() - score_start) * 1000)
        deltas = _score_deltas(before_scores, after_scores)

        replay = ReplayRecord(
            run_type="representation.optimize",
            inputs={"query": query, "count": len(evidence_products), "tone": tone},
            outputs={"count": len(optimized_pairs)},
            tool_calls=[
                ToolCall(
                    name="optimize_representation",
                    arguments={"count": len(evidence_products)},
                    result_summary="before_after_pairs",
                    elapsed_ms=optimize_ms,
                ),
                ToolCall(
                    name="score_products",
                    arguments={
                        "goal_count": len(goals),
                        "product_count": len(before_products),
                    },
                    result_summary="alignment_deltas",
                    elapsed_ms=score_ms,
                ),
            ],
            versions=default_versions(),
        )
        replay_id = None
        if client_id:
            replay_id = replays_repo.create_replay_record(
                run_type="representation.optimize",
                record=replay.to_dict(),
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
                entity_type="evidence_flow",
                entity_id=query or "unknown",
            ).get("id")

        return {
            "intent": intent,
            "goals": goals,
            "optimized": optimized_pairs,
            "alignment_deltas": deltas,
            "replay": replay.to_dict(),
            "replay_id": replay_id,
        }

    def verify_recommendations(
        self,
        *,
        query: str,
        evidence_products: List[EvidenceProduct],
        optimized: Optional[List[Dict[str, Any]]] = None,
        client_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        classifier = HybridIntentClassifier()
        intent = classifier.classify(query).to_dict()
        goals = _intent_goals(intent, fallback=query)

        before_products = [to_product(item) for item in evidence_products]
        score_start = time.perf_counter()
        before_scores = goal_alignment.score_products(goals, before_products)

        optimized_pairs = optimized or []
        after_products = before_products
        if optimized_pairs:
            after_products = [
                _product_with_description(
                    product, pair.get("after") or product.description
                )
                for product, pair in zip(before_products, optimized_pairs)
            ]
        after_scores = goal_alignment.score_products(goals, after_products)
        score_ms = int((time.perf_counter() - score_start) * 1000)

        predicted = _ranked_ids(after_scores)
        actual = simulate_actual(after_products)
        lift = average_alignment(after_scores) - average_alignment(before_scores)

        replay = ReplayRecord(
            run_type="recommendation.verify",
            inputs={
                "query": query,
                "count": len(evidence_products),
                "optimized": bool(optimized),
            },
            outputs={"lift": round(lift, 3)},
            tool_calls=[
                ToolCall(
                    name="score_products",
                    arguments={
                        "goal_count": len(goals),
                        "product_count": len(after_products),
                    },
                    result_summary="predicted_vs_actual",
                    elapsed_ms=score_ms,
                )
            ],
            versions=default_versions(),
        )
        replay_id = None
        if client_id:
            replay_id = replays_repo.create_replay_record(
                run_type="recommendation.verify",
                record=replay.to_dict(),
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
                entity_type="evidence_flow",
                entity_id=query,
            ).get("id")

        return {
            "intent": intent,
            "goals": goals,
            "predicted": predicted,
            "actual": actual,
            "lift": round(lift, 3),
            "baseline_alignment": [score.__dict__ for score in before_scores],
            "optimized_alignment": [score.__dict__ for score in after_scores],
            "replay": replay.to_dict(),
            "replay_id": replay_id,
        }


def _intent_goals(intent: dict, fallback: str | None = None) -> List[str]:
    goals: List[str] = []
    primary = intent.get("primary_goal") or intent.get("label")
    if primary and primary != "unknown":
        goals.append(primary)
    goals.extend(intent.get("secondary_goals") or [])
    goals.extend(intent.get("underlying_needs") or [])
    deduped = list(dict.fromkeys([goal for goal in goals if goal]))
    if not deduped and fallback:
        deduped = [fallback]
    return deduped


def _evidence_to_dict(item: EvidenceProduct) -> Dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "source": item.source,
        "url": item.url,
        "price": item.price,
        "confidence": item.confidence,
        "raw_text": item.raw_text,
        "metadata": item.metadata,
    }


def _product_with_description(product, description: str):
    return type(product)(**{**product.__dict__, "description": description})


def _score_deltas(before, after):
    before_map = {score.product_id: score.score for score in before}
    deltas = []
    for score in after:
        baseline = before_map.get(score.product_id, 0.0)
        deltas.append(
            {
                "product_id": score.product_id,
                "before": baseline,
                "after": score.score,
                "delta": round(score.score - baseline, 3),
            }
        )
    return deltas


def _ranked_ids(scores):
    ordered = sorted(scores, key=lambda s: s.score, reverse=True)
    return [score.product_id for score in ordered]
