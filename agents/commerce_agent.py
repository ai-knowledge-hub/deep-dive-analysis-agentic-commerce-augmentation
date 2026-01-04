"""Agent that orchestrates search and comparison within the commerce core."""

from __future__ import annotations

from typing import List

from src.products import search as product_search
from src.products.compare import compare


class CommerceAgent:
    def build_plan(self, intent: dict) -> dict:
        query = intent.get("label", "workspace")
        products = product_search.search(query)
        comparison = compare(products[:2])
        return {
            "query": query,
            "product_ids": [product.id for product in products],
            "comparison": comparison,
        }

    def recommend(self, query: str) -> List[str]:
        return [product.name for product in product_search.search(query)]
