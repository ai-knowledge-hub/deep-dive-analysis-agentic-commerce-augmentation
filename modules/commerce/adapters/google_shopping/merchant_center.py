"""Adapter for Google Merchant Center feed ingestion (JSON example)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from modules.commerce.domain import Product, RawOffer
from modules.commerce.adapters.transformers import convert_offers, transform_catalog

REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "link",
    "image_link",
    "price",
    "availability",
}


def _parse_price(value: str) -> tuple[float, str]:
    amount, _, currency = value.partition(" ")
    return float(amount), (currency or "USD")


def _validate_entry(entry: dict) -> None:
    missing = REQUIRED_FIELDS - entry.keys()
    if missing:
        raise ValueError(
            f"Missing required Merchant Center fields: {', '.join(sorted(missing))}"
        )


def _entry_to_offer(entry: dict) -> RawOffer:
    _validate_entry(entry)
    price, currency = _parse_price(entry["price"])
    attributes = {
        "capabilities": entry.get("capabilities", []),
        "empowerment_scores": entry.get("empowerment_scores", {}),
        "tags": [entry.get("google_product_category", "")],
        "brand_override": entry.get("brand"),
    }
    return RawOffer(
        source="google_merchant",
        source_id=str(entry["id"]),
        merchant_name=entry.get("brand"),
        offer_url=entry.get("link"),
        title=entry.get("title", "Unnamed Product"),
        description=entry.get("description"),
        price=price,
        currency=currency,
        availability=entry.get("availability", "unknown"),
        inventory_quantity=None,
        variant_attributes={"brand": entry.get("brand")},
        media=[entry.get("image_link", "")],
        attributes=attributes,
        confidence=0.8,
        completeness=0.7,
        inferred_fields=[
            key for key in ["capabilities", "empowerment_scores"] if key not in entry
        ],
    )


def load_offers(path: str | None = None) -> List[RawOffer]:
    feed_path = path or os.getenv("GOOGLE_MERCHANT_FEED_PATH")
    if not feed_path:
        raise RuntimeError(
            "GOOGLE_MERCHANT_FEED_PATH must be set for google_merchant source"
        )
    entries = json.loads(Path(feed_path).read_text(encoding="utf-8"))
    return [_entry_to_offer(entry) for entry in entries]


def load_catalog(path: str | None = None) -> List[Product]:
    offers = load_offers(path)
    raw_products = convert_offers(offers)
    return transform_catalog(raw_products)
