"""Local JSON loader that mimics a feed adapter for demos/tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from modules.commerce.domain import Product
from modules.intentionality.profiling import build_profile

CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "sample_catalog_discovery.json"
)


def load_catalog(path: Path = CATALOG_PATH) -> List[Product]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    products = [Product(**item) for item in payload]
    for product in products:
        product.intentionality_profile = build_profile(product).to_dict()
    return products
