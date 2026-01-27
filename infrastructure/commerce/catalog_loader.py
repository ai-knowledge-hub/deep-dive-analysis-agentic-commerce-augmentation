"""Registry for loading catalogs from different data sources.

This is an infrastructure concern (IO + env selection). Adapter implementations
may still live under `modules/` during migration; this module is the stable
entrypoint for application services.
"""

from __future__ import annotations

import os
from typing import Callable, List

from domain.commerce.types import Product


CatalogLoader = Callable[[], List[Product]]

_SOURCE_MAP: dict[str, CatalogLoader] = {}


def register_source(name: str, loader: CatalogLoader) -> None:
    _SOURCE_MAP[name] = loader


def load_catalog(source: str | None = None) -> List[Product]:
    source_name = (source or os.getenv("CATALOG_SOURCE", "mock")).lower()
    if source_name == "mock":
        # Intentional: avoid misleading demo catalog results.
        return []

    if source_name not in _SOURCE_MAP:
        if source_name == "shopify":
            from infrastructure.commerce.adapters.shopify import (
                load_catalog as load_shopify,
            )

            _SOURCE_MAP["shopify"] = load_shopify
        elif source_name in {"google", "google_shopping"}:
            from infrastructure.commerce.adapters.google_shopping import (
                load_catalog as load_google,
            )

            _SOURCE_MAP[source_name] = load_google
        elif source_name in {"google_merchant", "google_mc"}:
            from infrastructure.commerce.adapters.google_shopping import (
                load_merchant_catalog,
            )

            _SOURCE_MAP[source_name] = load_merchant_catalog
        elif source_name in {"ucp"}:
            from infrastructure.commerce.adapters.ucp import load_catalog as load_ucp

            _SOURCE_MAP[source_name] = load_ucp
        else:
            raise ValueError(f"Unknown catalog source: {source_name}")

    return _SOURCE_MAP[source_name]()
