from __future__ import annotations

import json

from application.services.workflow_portability.measurement import (
    MEASUREMENT_SCHEMA_VERSION,
    canonical_measurement_json,
    measurements_passed,
    run_portability_measurements,
)
from domain.workflow.portability import PORTABILITY_CONTRACT_VERSION


def test_measurement_runner_emits_canonical_raw_samples_for_both_adapters(tmp_path):
    measurements = run_portability_measurements(
        output_directory=tmp_path / "measurement-data",
        sample_count=2,
    )
    encoded = canonical_measurement_json(measurements)

    assert json.loads(encoded) == measurements
    assert encoded == canonical_measurement_json(json.loads(encoded))
    assert measurements["measurement_schema_version"] == MEASUREMENT_SCHEMA_VERSION
    assert measurements["portability_contract_version"] == PORTABILITY_CONTRACT_VERSION
    assert measurements_passed(measurements)
    assert [item["adapter_id"] for item in measurements["adapters"]] == [
        "internal-kernel.v2",
        "sqlite-portability.v1",
    ]
    for adapter in measurements["adapters"]:
        assert adapter["required_packages"] == []
        assert adapter["external_services"] == []
        assert len(adapter["samples"]) == 2
        for sample in adapter["samples"]:
            assert sample["passed"] is True
            assert sample["cold_start_latency_ns"] >= 0
            assert sample["recovery_latency_ns"] >= 0
            assert sample["evidence_counts"] == {
                "checkpoints": 2,
                "command_receipts": 4,
                "commands": 4,
                "effect_receipts": 1,
                "events": 4,
            }
    sqlite_result = measurements["adapters"][1]
    assert sqlite_result["connection_settings"] == {
        "busy_timeout_ms": 5000,
        "foreign_keys": True,
        "journal_mode": "wal",
        "synchronous": "full",
    }
    assert all(
        sample["persisted_database_bytes"] > 0 for sample in sqlite_result["samples"]
    )


def test_measurement_runner_rejects_nonpositive_sample_count(tmp_path):
    for sample_count in (0, -1, True):
        try:
            run_portability_measurements(
                output_directory=tmp_path,
                sample_count=sample_count,
            )
        except ValueError as exc:
            assert "positive integer" in str(exc)
        else:
            raise AssertionError("nonpositive sample count was accepted")


def test_measurement_runner_isolates_repeated_invocations(tmp_path):
    output_directory = tmp_path / "measurement-data"

    first = run_portability_measurements(
        output_directory=output_directory,
        sample_count=2,
    )
    second = run_portability_measurements(
        output_directory=output_directory,
        sample_count=2,
    )

    assert measurements_passed(first)
    assert measurements_passed(second)
    run_directories = sorted(
        path for path in output_directory.iterdir() if path.name.startswith("run-")
    )
    assert len(run_directories) == 2
    for run_directory in run_directories:
        assert sorted(path.name for path in run_directory.glob("*.sqlite3")) == [
            "sqlite-sample-0.sqlite3",
            "sqlite-sample-1.sqlite3",
        ]
