"""MCP tool wrapper for product search."""

from __future__ import annotations

from src.products import search as product_search


def run(query: str) -> dict:
    results = product_search.search(query)
    return {"results": [product.__dict__ for product in results]}
