"""Application-level commerce plan builder.

This is the orchestration layer for producing a recommendation plan from:
- inferred intent
- clarified goals
- product search results

It is dependency-injected so we can keep `modules/*` as compatibility shims.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Protocol, Tuple


class _Product(Protocol):
    id: str
    name: str
    price: float | None
    confidence: float
    source: str
    tags: list[str]
    description: str
    merchant_name: str | None
    offer_url: str | None
    capabilities_enabled: list[str]
    intentionality_profile: Any | None


SearchFn = Callable[[str], List[_Product]]
CompareFn = Callable[[List[_Product]], Any]
BuildProfileFn = Callable[[_Product], Any]


class CommercePlanBuilder:
    """Builds product recommendation plans based on intent and goals."""

    confidence_threshold: float = 0.65
    fallback_limit: int = 3

    def __init__(
        self,
        *,
        search_fn: SearchFn,
        compare_fn: CompareFn,
        build_profile_fn: BuildProfileFn,
    ) -> None:
        self._search_fn = search_fn
        self._compare_fn = compare_fn
        self._build_profile_fn = build_profile_fn

    def build_plan(
        self,
        *,
        intent: dict,
        goals: Optional[List[str]] = None,
        context: str | None = None,
        reason_fn=None,
        assess_fn=None,
        score_fn=None,
    ) -> dict:
        goal_signals = self._intent_goals(intent, goals)
        queries = self._derive_queries(intent, goal_signals)
        fallback_reason = None
        query = queries[0] if queries else "workspace"
        products: List[_Product] = []

        for candidate in queries:
            candidate_products = self._search_fn(candidate)
            if candidate_products:
                products = candidate_products
                query = candidate
                if candidate != queries[0]:
                    fallback_reason = (
                        f"No products for '{queries[0]}', fell back to '{candidate}'."
                    )
                break

        selected_products, filtered_count = self._select_products(products)
        per_product_alignment = (
            self._per_product_alignment(goal_signals, selected_products, score_fn)
            if goal_signals
            else {}
        )
        enrichment = self._product_summaries(selected_products, per_product_alignment)

        if reason_fn:
            annotated = (
                reason_fn(goal_signals or [], enrichment, context=context) or enrichment
            )
        else:
            annotated = enrichment

        comparison = self._compare_fn(selected_products[:2])
        data_quality = self._data_quality(annotated)
        data_quality["filtered_low_confidence"] = filtered_count
        clarifications = self._clarifications(
            annotated, data_quality, filtered_count, fallback_reason
        )
        alignment = self._alignment_snapshot(goal_signals, selected_products, assess_fn)

        return {
            "query": query,
            "products": annotated,
            "product_explanations": self._product_explanations(annotated),
            "comparison": comparison,
            "data_quality": data_quality,
            "clarifications": clarifications,
            "alignment": alignment,
        }

    def _derive_queries(self, intent: dict, goals: List[str]) -> List[str]:
        label = intent.get("primary_goal") or intent.get("label", "")
        domain = intent.get("domain", "")
        candidates = []
        if label and label != "unknown":
            candidates.append(label.replace("_", " "))
        if goals:
            candidates.extend([goal for goal in goals[:2] if goal != "unknown"])
        if domain and domain not in candidates:
            candidates.append(domain)
        candidates.append("workspace")
        return [candidate for candidate in candidates if candidate]

    def _intent_goals(self, intent: dict, goals: Optional[List[str]]) -> List[str]:
        merged: List[str] = []
        if goals:
            merged.extend(goals)
        primary = intent.get("primary_goal") or intent.get("label")
        if primary and primary != "unknown":
            merged.append(primary)
        merged.extend(intent.get("secondary_goals") or [])
        merged.extend(intent.get("underlying_needs") or [])
        seen: set[str] = set()
        deduped: List[str] = []
        for goal in merged:
            if goal and goal != "unknown" and goal not in seen:
                seen.add(goal)
                deduped.append(goal)
        return deduped

    def _select_products(self, products: List[_Product]) -> Tuple[List[_Product], int]:
        sorted_products = sorted(
            products, key=lambda product: product.confidence, reverse=True
        )
        filtered_products = [
            product
            for product in sorted_products
            if product.confidence >= self.confidence_threshold
        ]
        filtered_count = len(sorted_products) - len(filtered_products)
        if not filtered_products:
            filtered_products = sorted_products[: self.fallback_limit]
            filtered_count = 0
        return filtered_products, max(filtered_count, 0)

    def _product_summaries(
        self, products: List[_Product], alignment_scores: dict[str, dict]
    ) -> List[dict]:
        summaries: List[dict] = []
        for product in products:
            profile = product.intentionality_profile
            if profile is None:
                profile = self._build_profile_fn(product).to_dict()
            summaries.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "confidence": product.confidence,
                    "source": product.source,
                    "merchant_name": product.merchant_name,
                    "offer_url": product.offer_url,
                    "capabilities_enabled": product.capabilities_enabled,
                    "alignment_score": alignment_scores.get(product.id, {}).get("score"),
                    "alignment_reasoning": alignment_scores.get(product.id, {}).get(
                        "alignment_reasoning"
                    ),
                    "intentionality_profile": profile,
                }
            )
        return summaries

    def _data_quality(self, products: List[dict]) -> dict:
        if not products:
            return {
                "average_confidence": 0.0,
                "sources": [],
                "filtered_low_confidence": 0,
            }
        confidence = sum(product["confidence"] for product in products) / len(products)
        sources = sorted({product["source"] for product in products})
        return {
            "average_confidence": round(confidence, 2),
            "sources": sources,
            "filtered_low_confidence": 0,
        }

    def _clarifications(
        self,
        products: List[dict],
        data_quality: dict,
        filtered_count: int,
        fallback_reason: str | None,
    ) -> List[str]:
        clarifications: List[str] = []
        avg_conf = data_quality.get("average_confidence", 0.0) or 0.0
        if avg_conf < 0.75:
            clarifications.append(
                "Data confidence is low; request merchant-verified options or additional context."
            )
        if filtered_count > 0:
            clarifications.append(
                f"{filtered_count} low-confidence products were hidden from the plan."
            )
        if any(product["source"] != "shopify" for product in products):
            clarifications.append(
                "Some recommendations come from discovery surfaces (e.g., Google Shopping). Confirm availability before purchasing."
            )
        if fallback_reason:
            clarifications.append(fallback_reason)
        if not clarifications:
            clarifications.append(
                "All recommendations are merchant-verified with high confidence."
            )
        return clarifications

    def _alignment_snapshot(
        self, goals: List[str], products: List[_Product], assess_fn=None
    ) -> dict:
        if not goals or not products:
            return {
                "goal_alignment": {
                    "score": 0.0,
                    "aligned_goals": [],
                    "misaligned_goals": goals or [],
                    "supporting_products": [],
                    "confidence_summary": {
                        "average_confidence": 0.0,
                        "aligned_goal_confidence": {},
                    },
                    "baseline_score": 0.0,
                }
            }

        if assess_fn:
            result = assess_fn(goals, products)
            baseline_score = 0.0
            try:
                baseline = assess_fn(goals, products, use_semantic=False)
                baseline_score = baseline.score
            except TypeError:
                baseline_score = 0.0
            return {
                "goal_alignment": {
                    "score": result.score,
                    "aligned_goals": result.aligned_goals,
                    "misaligned_goals": result.misaligned_goals,
                    "supporting_products": result.supporting_products,
                    "confidence_summary": result.confidence_summary,
                    "baseline_score": baseline_score,
                }
            }

        return {
            "goal_alignment": {
                "score": 0.0,
                "aligned_goals": [],
                "misaligned_goals": goals,
                "supporting_products": [],
                "confidence_summary": {
                    "average_confidence": 0.0,
                    "aligned_goal_confidence": {},
                },
                "baseline_score": 0.0,
            }
        }

    def _per_product_alignment(
        self, goals: List[str], products: List[_Product], score_fn=None
    ) -> dict[str, dict]:
        if not goals or not products or not score_fn:
            return {}
        scores = score_fn(goals, products) or []
        out: dict[str, dict] = {}
        for score in scores:
            pid = score.get("product_id")
            if not pid:
                continue
            out[pid] = {
                "product_id": pid,
                "score": score.get("score"),
                "alignment_reasoning": score.get("alignment_reasoning"),
                "confidence": score.get("confidence"),
            }
        return out

    def _product_explanations(self, products: List[dict]) -> dict:
        return {
            "count": len(products),
            "avg_confidence": (
                round(sum(p["confidence"] for p in products) / len(products), 2)
                if products
                else 0.0
            ),
        }


__all__ = ["CommercePlanBuilder"]

