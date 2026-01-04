"""Agent that orchestrates search and comparison within the commerce core."""

from __future__ import annotations
from typing import List

from src.products import search as product_search
from src.products.compare import compare


class CommerceAgent:
    confidence_threshold: float = 0.65
    fallback_limit: int = 3

    def build_plan(self, intent: dict) -> dict:
        query = intent.get("label", "workspace")
        products = product_search.search(query)
        selected_products, filtered_count = self._select_products(products)
        enriched_products = [self._product_summary(product) for product in selected_products]
        comparison = compare(selected_products[:2])
        data_quality = self._data_quality(enriched_products)
        data_quality["filtered_low_confidence"] = filtered_count
        clarifications = self._clarifications(enriched_products, data_quality, filtered_count)
        return {
            "query": query,
            "products": enriched_products,
            "comparison": comparison,
            "data_quality": data_quality,
            "clarifications": clarifications,
        }

    def recommend(self, query: str) -> List[str]:
        return [product.name for product in product_search.search(query)]

    def _product_summary(self, product) -> dict:
        summary = {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "confidence": product.confidence,
            "source": product.source,
            "merchant_name": product.merchant_name,
            "offer_url": product.offer_url,
            "capabilities_enabled": product.capabilities_enabled,
        }
        return summary

    def _select_products(self, products):
        sorted_products = sorted(products, key=lambda product: product.confidence, reverse=True)
        filtered_products = [product for product in sorted_products if product.confidence >= self.confidence_threshold]
        filtered_count = len(sorted_products) - len(filtered_products)
        if not filtered_products:
            filtered_products = sorted_products[: self.fallback_limit]
            filtered_count = 0
        return filtered_products, max(filtered_count, 0)

    def _data_quality(self, products: List[dict]) -> dict:
        if not products:
            return {"average_confidence": 0.0, "sources": [], "filtered_low_confidence": 0}
        confidence = sum(product["confidence"] for product in products) / len(products)
        sources = sorted({product["source"] for product in products})
        return {
            "average_confidence": round(confidence, 2),
            "sources": sources,
            "filtered_low_confidence": 0,
        }

    def _clarifications(self, products: List[dict], data_quality: dict, filtered_count: int) -> List[str]:
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
        if not clarifications:
            clarifications.append("All recommendations are merchant-verified with high confidence.")
        return clarifications
