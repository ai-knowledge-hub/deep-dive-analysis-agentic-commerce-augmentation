"""Local JSON loader that mimics a feed adapter for demos/tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from modules.commerce.domain import Product

CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "sample_catalog_empowerment.json"


def load_catalog(path: Path = CATALOG_PATH) -> List[Product]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [Product(**item) for item in payload]
