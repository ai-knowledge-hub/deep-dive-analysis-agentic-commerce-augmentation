from __future__ import annotations

import sys
import types

if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")
    genai_pkg.Client = lambda *args, **kwargs: None
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from api.composition import default_deps
from application.services.memory_service import MemoryService
from shared.db.connection import init_db, set_database_path


def test_memory_distill_threshold_and_retrieve_precedence(tmp_path):
    db_path = tmp_path / "memory-service.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    deps.clients.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    deps.clients.create_product(
        product_id="product-a",
        brand_id="brand-a",
        name="Product A",
        metadata={"vertical": "sports_apparel"},
    )
    service = MemoryService(deps=deps)

    low = service.distill(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        vertical="sports_apparel",
        artifact_type="query_pattern",
        payload={"query_template": "low quality"},
        quality_score=0.5,
        support_count=1,
        source="manual",
    )
    assert low["is_promoted"] is False

    global_vertical = service.distill(
        client_id="client-a",
        vertical="sports_apparel",
        artifact_type="query_pattern",
        payload={"query_template": "vertical global"},
        quality_score=0.9,
        support_count=5,
        source="manual",
    )
    brand_vertical = service.distill(
        client_id="client-a",
        brand_id="brand-a",
        vertical="sports_apparel",
        artifact_type="query_pattern",
        payload={"query_template": "brand vertical"},
        quality_score=0.9,
        support_count=5,
        source="manual",
    )
    product_specific = service.distill(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        vertical="sports_apparel",
        artifact_type="query_pattern",
        payload={"query_template": "product specific"},
        quality_score=0.9,
        support_count=5,
        source="manual",
    )

    retrieved = service.retrieve(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        vertical="sports_apparel",
        artifact_type="query_pattern",
        min_quality=0.65,
        limit=10,
    )
    ids = [item["id"] for item in retrieved]
    assert product_specific["id"] in ids
    assert brand_vertical["id"] in ids
    assert global_vertical["id"] in ids
    assert low["id"] not in ids
    assert ids.index(product_specific["id"]) < ids.index(brand_vertical["id"])
    assert ids.index(brand_vertical["id"]) < ids.index(global_vertical["id"])
