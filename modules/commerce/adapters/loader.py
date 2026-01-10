"""Registry for loading catalogs from different data sources."""

from __future__ import annotations

import os
from typing import List

from modules.commerce.domain import Product
from modules.commerce.adapters.mock import load_catalog as load_mock_catalog

_SOURCE_MAP = {
    "mock": load_mock_catalog,
}


def register_source(name: str, loader):
    _SOURCE_MAP[name] = loader


def load_catalog(source: str | None = None) -> List[Product]:
    source_name = (source or os.getenv("CATALOG_SOURCE", "mock")).lower()
    if source_name not in _SOURCE_MAP:
        if source_name == "shopify":
            from modules.commerce.adapters.shopify import load_catalog as load_shopify

            _SOURCE_MAP["shopify"] = load_shopify
        elif source_name in {"google", "google_shopping"}:
            from modules.commerce.adapters.google_shopping import load_catalog as load_google

            _SOURCE_MAP[source_name] = load_google
        elif source_name in {"google_merchant", "google_mc"}:
            from modules.commerce.adapters.google_shopping import load_merchant_catalog

            _SOURCE_MAP[source_name] = load_merchant_catalog
        else:
            raise ValueError(f"Unknown catalog source: {source_name}")
    loader = _SOURCE_MAP[source_name]
    return loader()
