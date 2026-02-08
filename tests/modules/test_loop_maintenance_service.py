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
from application.services.loop.loop_maintenance_service import LoopMaintenanceService
from shared.db.connection import init_db, set_database_path


def test_loop_maintenance_refreshes_calibration_and_distills_memory(tmp_path):
    db_path = tmp_path / "loop-maintenance.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    deps.clients.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    deps.clients.create_product(
        product_id="product-a", brand_id="brand-a", name="Product A", description="desc"
    )

    in_app_job = deps.validation_jobs.create_job(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        entity_type="experiment",
        entity_id="exp-1",
        provider="openrouter",
        mode="in_app",
        model="openai/gpt-oss-120b",
        prompt_version="v1",
        status="completed",
        input_payload={},
        requested_by="user-a",
    )
    deps.validation_results.create_result(
        job_id=in_app_job["id"],
        provider="openrouter",
        model="openai/gpt-oss-120b",
        structured_result={"score": 0.55},
        raw_response=None,
        score=0.55,
        winner_id="v1",
        evidence_strength="weak",
        latency_ms=10,
        cost_usd=0.0,
    )
    observed_job = deps.validation_jobs.create_job(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        entity_type="experiment",
        entity_id="exp-1",
        provider="openrouter",
        mode="external",
        model="openai/gpt-oss-120b",
        prompt_version="v1",
        status="completed",
        input_payload={},
        requested_by="user-a",
    )
    deps.validation_results.create_result(
        job_id=observed_job["id"],
        provider="openrouter",
        model="openai/gpt-oss-120b",
        structured_result={"score": 0.81},
        raw_response=None,
        score=0.81,
        winner_id="v2",
        evidence_strength="strong",
        latency_ms=9,
        cost_usd=0.0,
    )
    deps.belief_revisions.create_belief_revision(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        hypothesis_key="validation:experiment:exp-1",
        prior=0.5,
        likelihood=0.8,
        posterior=0.77,
        confidence=0.82,
        evidence_ref={
            "provider": "openrouter",
            "support_size": 3,
            "vertical": "sports",
        },
    )

    service = LoopMaintenanceService(deps=deps)
    profiles = service.refresh_calibration_profiles(client_id="client-a")
    assert profiles
    assert profiles[0]["provider"] == "openrouter"
    assert 0.0 <= float(profiles[0]["drift_score"]) <= 1.0

    artifacts = service.distill_recent_beliefs(client_id="client-a")
    assert artifacts
    assert artifacts[0]["artifact_type"] == "audience_pattern"
    assert bool(artifacts[0]["is_promoted"]) is True
