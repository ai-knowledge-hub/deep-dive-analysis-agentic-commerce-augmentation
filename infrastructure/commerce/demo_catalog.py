"""Demo catalog loader for tests and local demos.

Note: `infrastructure.commerce.catalog_loader` intentionally disables the
`mock` source for the end-user app to avoid misleading recommendations.
This loader exists for deterministic tests and seeded demo experiences.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from domain.commerce.types import Product
from domain.intentionality.profiling import fallback_profile_for_product


CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "sample_catalog_discovery.json"
)


def load_demo_catalog(path: Path = CATALOG_PATH) -> List[Product]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    products = [Product(**item) for item in payload]
    for product in products:
        product.intentionality_profile = fallback_profile_for_product(product).to_dict()
    return products


__all__ = ["load_demo_catalog"]
