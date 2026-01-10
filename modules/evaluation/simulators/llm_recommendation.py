"""Simulator that replays shopping intents against different representations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from modules.commerce.domain import Product
from modules.commerce import search as product_search


@dataclass
class SimulationResult:
    intent_id: str
    query: str
    product_ids: List[str]
    average_confidence: float


def run_simulation(intent_id: str, query: str, limit: int = 3) -> SimulationResult:
    products = product_search.search(query, limit=limit)
    average_confidence = sum(product.confidence for product in products) / max(len(products), 1)
    return SimulationResult(
        intent_id=intent_id,
        query=query,
        product_ids=[product.id for product in products],
        average_confidence=average_confidence,
    )
