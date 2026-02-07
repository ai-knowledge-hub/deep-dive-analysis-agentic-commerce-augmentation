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
from application.services.belief_update_service import BeliefUpdateService
from application.services.belief_update_service import bayesian_posterior
from shared.db.connection import init_db, set_database_path


def test_bayesian_posterior_bounds():
    assert 0.0 <= bayesian_posterior(0.0, 0.0) <= 1.0
    assert 0.0 <= bayesian_posterior(1.0, 1.0) <= 1.0
    assert 0.0 <= bayesian_posterior(-1.0, 2.0) <= 1.0


def test_bayesian_posterior_moves_with_evidence():
    low = bayesian_posterior(0.5, 0.2)
    high = bayesian_posterior(0.5, 0.8)
    assert high > low


def test_calibration_profile_influences_belief_confidence(tmp_path):
    db_path = tmp_path / "belief-calibration.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    service = BeliefUpdateService(deps=deps)

    baseline = service.update(
        client_id="client-a",
        hypothesis_key="calibration:test",
        evidence={
            "source": "synthetic",
            "provider": "openrouter",
            "score": 0.8,
            "confidence": 0.8,
            "support_size": 3,
        },
    )

    deps.calibration_profiles.upsert_calibration_profile(
        client_id="client-a",
        provider="openrouter",
        metric_weights={"score_weight": 0.6, "confidence_weight": 0.6},
        drift_score=0.9,
    )
    calibrated = service.update(
        client_id="client-a",
        hypothesis_key="calibration:test",
        evidence={
            "source": "synthetic",
            "provider": "openrouter",
            "score": 0.8,
            "confidence": 0.8,
            "support_size": 3,
        },
    )
    assert calibrated["confidence"] < baseline["confidence"]
