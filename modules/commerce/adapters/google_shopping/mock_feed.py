"""Mock Google Shopping adapter emitting RawOffer objects for testing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from modules.commerce.domain import Product, RawOffer
from modules.commerce.adapters.transformers import convert_offers, transform_catalog

_MOCK_PATH = Path(__file__).resolve().parents[4] / "data" / "google_shopping_mock.json"


def load_mock_offers(path: Path = _MOCK_PATH) -> List[RawOffer]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    offers: List[RawOffer] = []
    for entry in payload:
        offers.append(
            RawOffer(
                source="google_shopping",
                source_id=entry["source_id"],
                merchant_name=entry.get("merchant_name"),
                offer_url=entry.get("offer_url"),
                title=entry["title"],
                description=entry.get("description"),
                price=float(entry.get("price", 0)),
                currency=entry.get("currency", "USD"),
                availability=entry.get("availability", "unknown"),
                inventory_quantity=None,
                variant_attributes=entry.get("variant_attributes", {}),
                media=entry.get("media", []),
                attributes=entry.get("attributes", {}),
                confidence=float(entry.get("confidence", 0.6)),
                completeness=float(entry.get("completeness", 0.7)),
                inferred_fields=entry.get("inferred_fields", []),
            )
        )
    return offers


def load_catalog() -> List[Product]:
    offers = load_mock_offers()
    raw_products = convert_offers(offers)
    return transform_catalog(raw_products)
