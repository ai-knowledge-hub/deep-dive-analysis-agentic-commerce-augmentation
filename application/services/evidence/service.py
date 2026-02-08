from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from shared.replay.versions import default_versions
from domain.intent.goals import extract_intent_goals
from domain.simulation import ranking as domain_ranking
from shared.agents.replay_logger import ReplayLogger, ReplayRecord, ToolCall
from domain.evidence.types import EvidenceProduct
from application.ports.deps import AppDeps
from application.services.evidence.alignment_service import AlignmentService
from application.services.evidence.retriever import retrieve as retrieve_evidence
from application.services.evidence.normalizer import to_product
from application.services.evidence.optimizer import optimize
from application.services.evidence.verify import average_alignment, simulate_actual
from application.services.evidence.intentionality_profiler import build_profile
from application.services.evidence.signal_extractor import SignalExtractor


class EvidenceService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._alignment = AlignmentService(deps)

    def analyze(
        self,
        *,
        query: str,
        max_items: int = 5,
        retrieve_fn=None,
        client_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        intent = self._deps.classify_intent(query)
        goals = extract_intent_goals(intent, fallback=query)

        start = time.perf_counter()
        if retrieve_fn is None:
            evidence_products = retrieve_evidence(
                query, max_items=max_items, run_research_fn=self._deps.run_research
            )
        else:
            evidence_products = retrieve_fn(query, max_items=max_items)
        retrieve_ms = int((time.perf_counter() - start) * 1000)
        products = [to_product(item) for item in evidence_products]
        profiles = [build_profile(product).to_dict() for product in products]
        score_start = time.perf_counter()
        alignment_scores = self._alignment.score_products(goals, products)
        score_ms = int((time.perf_counter() - score_start) * 1000)
        score_map = {score.product_id: score for score in alignment_scores}
        for item in evidence_products:
            score = score_map.get(item.id)
            if score:
                item.metadata["alignment_score"] = score.score
                item.metadata["alignment_reasoning"] = score.alignment_reasoning
                item.metadata["alignment_confidence"] = score.confidence
                item.confidence = _blend_confidence(
                    base=item.confidence,
                    alignment_score=score.score,
                    alignment_confidence=score.confidence,
                    item=item,
                )

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
            logger = ReplayLogger(persist_fn=self._deps.replays.create_replay_record)
            replay_id = logger.persist(
                run_type="evidence.analyze",
                record=replay,
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
            intent = self._deps.classify_intent(query)
            goals = extract_intent_goals(intent, fallback=query)

        start = time.perf_counter()
        optimized_pairs = optimize(
            evidence_products,
            generate_fn=self._deps.generate,
            build_optimization_prompt_fn=self._deps.build_optimization_prompt,
            goals=goals or None,
            tone=tone,
        )
        optimize_ms = int((time.perf_counter() - start) * 1000)

        before_products = [to_product(item) for item in evidence_products]
        after_products = [
            _product_with_description(product, pair["after"])
            for product, pair in zip(before_products, optimized_pairs)
        ]
        score_start = time.perf_counter()
        before_scores = self._alignment.score_products(goals, before_products)
        after_scores = self._alignment.score_products(goals, after_products)
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
            logger = ReplayLogger(persist_fn=self._deps.replays.create_replay_record)
            replay_id = logger.persist(
                run_type="representation.optimize",
                record=replay,
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
        intent = self._deps.classify_intent(query)
        goals = extract_intent_goals(intent, fallback=query)

        before_products = [to_product(item) for item in evidence_products]
        score_start = time.perf_counter()
        before_scores = self._alignment.score_products(goals, before_products)

        optimized_pairs = optimized or []
        after_products = before_products
        if optimized_pairs:
            after_products = [
                _product_with_description(
                    product, pair.get("after") or product.description
                )
                for product, pair in zip(before_products, optimized_pairs)
            ]
        after_scores = self._alignment.score_products(goals, after_products)
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
            logger = ReplayLogger(persist_fn=self._deps.replays.create_replay_record)
            replay_id = logger.persist(
                run_type="recommendation.verify",
                record=replay,
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

    def extract_signals(
        self,
        *,
        goal: str,
        product: Dict[str, Any],
        winner: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extractor = SignalExtractor(self._deps)
        result = extractor.extract(goal=goal, product=product, winner=winner)
        if not result:
            return {
                "intent_signals": [],
                "winner_signals": [],
                "missing_signals": [],
            }
        return {
            "intent_signals": result.intent_signals,
            "winner_signals": result.winner_signals,
            "missing_signals": result.missing_signals,
        }


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


def _blend_confidence(
    *,
    base: float,
    alignment_score: float,
    alignment_confidence: float,
    item: EvidenceProduct,
) -> float:
    def clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    description = item.description or ""
    desc_signal = min(len(description) / 200.0, 1.0) if description else 0.0
    url_signal = 1.0 if item.url else 0.0
    price_signal = 1.0 if item.price is not None else 0.0
    completeness = (0.6 * desc_signal) + (0.25 * url_signal) + (0.15 * price_signal)

    blended = (
        0.15 * clamp(base)
        + 0.45 * clamp(alignment_score)
        + 0.2 * clamp(alignment_confidence)
        + 0.2 * clamp(completeness)
    )
    return round(clamp(blended), 3)


def _product_with_description(product, description: str):
    return type(product)(**{**product.__dict__, "description": description})


def _score_deltas(before, after):
    deltas = []
    for score in after:
        baseline = 0.0
        for before_score in before:
            if before_score.product_id == score.product_id:
                baseline = before_score.score
                break
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
    ordered = domain_ranking.sort_scores([score.__dict__ for score in scores])
    return [item.get("product_id") for item in ordered if item.get("product_id")]
