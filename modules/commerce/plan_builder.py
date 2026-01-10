"""Commerce plan building logic - extracted from CommerceAgent.

This module contains the core business logic for building product recommendation plans,
including query derivation, product selection, data quality assessment, and empowerment snapshots.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from modules.commerce.domain import Product
from modules.commerce.search import search as product_search
from modules.commerce.compare import compare


class PlanBuilder:
    """Builds product recommendation plans based on intent and goals."""

    confidence_threshold: float = 0.65
    fallback_limit: int = 3

    def build_plan(
        self,
        intent: dict,
        goals: Optional[List[str]] = None,
        context: str | None = None,
        reason_fn=None,
        assess_fn=None,
    ) -> dict:
        """Build a complete recommendation plan.

        Args:
            intent: The detected user intent
            goals: List of user goals
            context: Session context string
            reason_fn: Optional function to reason about products (for LLM enrichment)
            assess_fn: Optional function to assess goal alignment

        Returns:
            Complete plan dictionary with products, clarifications, empowerment, etc.
        """
        queries = self._derive_queries(intent)
        fallback_reason = None
        query = queries[0] if queries else "workspace"
        products = []

        for candidate in queries:
            candidate_products = product_search(candidate)
            if candidate_products:
                products = candidate_products
                query = candidate
                if candidate != queries[0]:
                    fallback_reason = f"No products for '{queries[0]}', fell back to '{candidate}'."
                break

        selected_products, filtered_count = self._select_products(products)
        enrichment = self._product_summaries(selected_products)

        # Apply LLM reasoning if provided
        if reason_fn:
            annotated = reason_fn(goals or [], enrichment, context=context) or enrichment
        else:
            annotated = enrichment

        comparison = compare(selected_products[:2])
        data_quality = self._data_quality(annotated)
        data_quality["filtered_low_confidence"] = filtered_count
        clarifications = self._clarifications(annotated, data_quality, filtered_count, fallback_reason)

        # Compute empowerment snapshot
        empowerment = self._empowerment_snapshot(goals or [], selected_products, assess_fn)

        return {
            "query": query,
            "products": annotated,
            "product_explanations": self._product_explanations(annotated),
            "comparison": comparison,
            "data_quality": data_quality,
            "clarifications": clarifications,
            "empowerment": empowerment,
        }

    def _derive_queries(self, intent: dict) -> List[str]:
        """Derive search queries from intent."""
        label = intent.get("label", "")
        domain = intent.get("domain", "")
        candidates = []
        if label:
            candidates.append(label.replace("_", " "))
        if domain and domain not in candidates:
            candidates.append(domain)
        candidates.append("workspace")
        return [candidate for candidate in candidates if candidate]

    def _select_products(self, products: List[Product]) -> Tuple[List[Product], int]:
        """Select products based on confidence threshold."""
        sorted_products = sorted(products, key=lambda product: product.confidence, reverse=True)
        filtered_products = [
            product for product in sorted_products if product.confidence >= self.confidence_threshold
        ]
        filtered_count = len(sorted_products) - len(filtered_products)
        if not filtered_products:
            filtered_products = sorted_products[: self.fallback_limit]
            filtered_count = 0
        return filtered_products, max(filtered_count, 0)

    def _product_summaries(self, products: List[Product]) -> List[dict]:
        """Create summary dictionaries for products."""
        return [
            {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "confidence": product.confidence,
                "source": product.source,
                "merchant_name": product.merchant_name,
                "offer_url": product.offer_url,
                "capabilities_enabled": product.capabilities_enabled,
            }
            for product in products
        ]

    def _data_quality(self, products: List[dict]) -> dict:
        """Compute data quality metrics."""
        if not products:
            return {"average_confidence": 0.0, "sources": [], "filtered_low_confidence": 0}
        confidence = sum(product["confidence"] for product in products) / len(products)
        sources = sorted({product["source"] for product in products})
        return {
            "average_confidence": round(confidence, 2),
            "sources": sources,
            "filtered_low_confidence": 0,
        }

    def _clarifications(
        self, products: List[dict], data_quality: dict, filtered_count: int, fallback_reason: str | None
    ) -> List[str]:
        """Generate clarification messages based on plan quality."""
        clarifications: List[str] = []
        avg_conf = data_quality.get("average_confidence", 0.0) or 0.0
        if avg_conf < 0.75:
            clarifications.append(
                "Data confidence is low; request merchant-verified options or additional context."
            )
        if filtered_count > 0:
            clarifications.append(f"{filtered_count} low-confidence products were hidden from the plan.")
        if any(product["source"] != "shopify" for product in products):
            clarifications.append(
                "Some recommendations come from discovery surfaces (e.g., Google Shopping). Confirm availability before purchasing."
            )
        if fallback_reason:
            clarifications.append(fallback_reason)
        if not clarifications:
            clarifications.append("All recommendations are merchant-verified with high confidence.")
        return clarifications

    def _empowerment_snapshot(
        self, goals: List[str], products: List[Product], assess_fn=None
    ) -> dict:
        """Compute empowerment metrics for the plan."""
        if not goals or not products:
            return {
                "goal_alignment": {
                    "score": 0.0,
                    "aligned_goals": [],
                    "misaligned_goals": goals or [],
                    "supporting_products": [],
                    "confidence_summary": {"average_confidence": 0.0, "aligned_goal_confidence": {}},
                }
            }

        if assess_fn:
            result = assess_fn(goals, products)
            return {
                "goal_alignment": {
                    "score": result.score,
                    "aligned_goals": result.aligned_goals,
                    "misaligned_goals": result.misaligned_goals,
                    "supporting_products": result.supporting_products,
                    "confidence_summary": result.confidence_summary,
                }
            }

        # Fallback if no assess function provided
        return {
            "goal_alignment": {
                "score": 0.0,
                "aligned_goals": [],
                "misaligned_goals": goals,
                "supporting_products": [],
                "confidence_summary": {"average_confidence": 0.0, "aligned_goal_confidence": {}},
            }
        }

    def _product_explanations(self, products: List[dict]) -> List[dict]:
        """Extract product explanations from annotated products."""
        explanations: List[dict] = []
        for product in products or []:
            explanations.append(
                {
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "reasoning": product.get("reasoning", ""),
                    "capabilities_enabled": product.get("capabilities_enabled", []),
                    "confidence": product.get("confidence"),
                }
            )
        return explanations
