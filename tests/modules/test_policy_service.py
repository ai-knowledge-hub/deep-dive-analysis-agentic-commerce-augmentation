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
from application.services.loop.policy_service import PolicyService
from shared.db.connection import init_db, set_database_path


def test_policy_ranking_uses_calibration_weights(tmp_path):
    db_path = tmp_path / "policy-service.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    service = PolicyService(deps=deps)

    baseline = service.choose_action(
        client_id="client-a",
        provider="openrouter",
        uncertainty=0.8,
        expected_gain=0.8,
    )
    assert baseline["action"] in {
        "optimize_copy",
        "expand_battery",
        "validate",
        "clarify",
        "update_belief_only",
    }

    deps.calibration_profiles.upsert_calibration_profile(
        client_id="client-a",
        provider="openrouter",
        metric_weights={"gain_weight": 0.3, "uncertainty_weight": 1.5},
        drift_score=0.8,
    )
    calibrated = service.choose_action(
        client_id="client-a",
        provider="openrouter",
        uncertainty=0.8,
        expected_gain=0.8,
    )
    assert calibrated["action"] in {"validate", "clarify", "update_belief_only"}
