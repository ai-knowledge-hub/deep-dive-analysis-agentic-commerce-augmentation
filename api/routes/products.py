from __future__ import annotations

try:
    from fastapi import APIRouter, Query
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None  # type: ignore

from modules.commerce import search as product_search

if APIRouter:
    router = APIRouter(prefix="/products", tags=["products"])

    @router.get("/search")
    def search_products(query: str = Query("", max_length=128)):
        products = product_search.search(query)
        return [product.__dict__ for product in products]
else:  # pragma: no cover
    router = None
