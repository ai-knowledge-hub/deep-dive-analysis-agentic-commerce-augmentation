"""UCP catalog loader (mockable stub)."""

from __future__ import annotations

from typing import List
from pathlib import Path
import json

from modules.commerce.domain import Product
from modules.commerce.adapters.transformers import raw_product_to_product
from modules.commerce.domain import RawProduct


DEFAULT_UCP_MOCK = Path(__file__).resolve().parents[4] / "data" / "ucp_mock.json"


def _load_mock() -> List[RawProduct]:
    if not DEFAULT_UCP_MOCK.exists():
        return []
    payload = json.loads(DEFAULT_UCP_MOCK.read_text(encoding="utf-8"))
    products = []
    for entry in payload.get("items", []):
        products.append(
            RawProduct(
                product_id=entry.get("id", ""),
                sku=entry.get("id", ""),
                title=entry.get("title", ""),
                description=entry.get("description"),
                brand=entry.get("brand") or "",
                category=entry.get("category"),
                price=float(entry.get("price", 0.0)),
                currency=entry.get("currency", "USD"),
                availability=entry.get("availability", "unknown"),
                inventory_quantity=entry.get("inventory_quantity"),
                images=entry.get("images", []),
                attributes=entry.get("attributes", {}),
                source_metadata={"source": "ucp"},
                source="ucp",
                merchant_name=entry.get("merchant_name"),
                offer_url=entry.get("offer_url"),
                confidence=float(entry.get("confidence", 0.6)),
                completeness=float(entry.get("completeness", 0.6)),
            )
        )
    return products


def load_catalog() -> List[Product]:
    """Load catalog from a UCP merchant endpoint (mock for now)."""
    raw_products = _load_mock()
    return [raw_product_to_product(product) for product in raw_products]


__all__ = ["load_catalog"]
