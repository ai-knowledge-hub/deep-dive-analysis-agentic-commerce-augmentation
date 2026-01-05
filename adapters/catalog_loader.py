"""Registry for loading catalogs from different data sources."""

from __future__ import annotations

import os
from typing import List

from core.schema.product import Product

from adapters.mock.catalog_loader import load_catalog as load_mock_catalog

_SOURCE_MAP = {
    "mock": load_mock_catalog,
}


def register_source(name: str, loader):
    _SOURCE_MAP[name] = loader


def load_catalog(source: str | None = None) -> List[Product]:
    source_name = (source or os.getenv("CATALOG_SOURCE", "mock")).lower()
    if source_name not in _SOURCE_MAP:
        if source_name == "shopify":
            from adapters.shopify.catalog_loader import load_catalog as load_shopify

            _SOURCE_MAP["shopify"] = load_shopify
        elif source_name in {"google", "google_shopping"}:
            from adapters.google_shopping.mock_feed import load_catalog as load_google

            _SOURCE_MAP[source_name] = load_google
        elif source_name in {"google_merchant", "google_mc"}:
            from adapters.google_shopping.merchant_center import load_catalog as load_google_merchant

            _SOURCE_MAP[source_name] = load_google_merchant
        else:
            raise ValueError(f"Unknown catalog source: {source_name}")
    loader = _SOURCE_MAP[source_name]
    return loader()
